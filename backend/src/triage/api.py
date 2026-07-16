"""FastAPI application (BE-14).

Classification endpoints (which persist runs) plus read-only dashboard endpoints
that aggregate over stored artifacts. Provider-agnostic: the classifier is injected
via a cached dependency and can be overridden in tests with a fake provider.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from functools import lru_cache

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from evaluation.aggregator import aggregate_all, score_trend
from evaluation.storage import (
    ClassificationResult,
    RunRecord,
    list_evaluations,
    list_runs,
    save_run,
)

from .classifier import TriageClassifier
from .config import Settings, get_settings
from .logging_setup import configure_logging, current_log_file
from .prompts import PROMPT_VERSION
from .schemas import (
    AreaSugerida,
    Confianca,
    ProximaAcao,
    TipoSolicitacao,
    TriageInput,
    TriageOutput,
    Urgencia,
)

log = structlog.get_logger()


# In-memory background task status tracking
REPORT_TASK_STATUS = {
    "status": "idle",
    "progress": 0,
    "total": 0,
    "error": None,
    "result": None,
}


def background_run_reports(limit: int | None, settings: Settings):
    global REPORT_TASK_STATUS
    try:
        from evaluation.run_evaluation import resolve_targets, _evaluate_run, detect_regression
        from evaluation.judge import LLMJudge
        from evaluation.storage import list_evaluations, list_runs
        from evaluation.aggregator import aggregate_all
        from evaluation.reporter import generate_aggregate_report

        targets = resolve_targets(limit=limit)
        REPORT_TASK_STATUS["total"] = len(targets)
        REPORT_TASK_STATUS["progress"] = 0

        results = []
        if targets:
            judge = LLMJudge(settings)
            for i, run in enumerate(targets):
                record = _evaluate_run(run, judge)
                report = detect_regression(record, list_evaluations())
                results.append(
                    {
                        "run_id": run.run_id,
                        "total_items": len(run.results),
                        "score": round(report.current_score, 3),
                        "delta": round(report.delta, 3),
                        "baseline_score": round(report.baseline_score, 3),
                        "regressed": report.regressed,
                    }
                )
                REPORT_TASK_STATUS["progress"] = i + 1

        metrics = aggregate_all(list_evaluations(), list_runs())
        generate_aggregate_report(metrics)

        REPORT_TASK_STATUS["status"] = "completed"
        REPORT_TASK_STATUS["result"] = {
            "requested_limit": limit,
            "total_evaluated": len(results),
            "evaluated": results,
            "mean_overall_score": metrics.mean_overall_score,
            "total_evaluations": metrics.total_evaluations,
        }
    except Exception as e:
        log.exception("reports.run.failed", error=str(e))
        REPORT_TASK_STATUS["status"] = "failed"
        REPORT_TASK_STATUS["error"] = str(e)


class RunReportsRequest(BaseModel):
    """Trigger the offline evaluation cycle over pending runs.

    ``limit=None`` evaluates *all* pending runs; a positive ``limit`` evaluates
    only the ``N`` most recent pending runs.
    """

    limit: int | None = Field(default=None, ge=1)


# --- history DTOs ----------------------------------------------------------
# Clean, storage-agnostic contract for the history view. The frontend consumes
# only these shapes; persistence details (schema_version, eval_id, file names)
# never cross the API boundary.


class HistorySummary(BaseModel):
    run_id: str
    timestamp: str | None
    model: str | None
    prompt_version: str | None
    total_classifications: int
    mean_score: float | None
    evaluated: bool


class HistoryPage(BaseModel):
    total: int
    items: list[HistorySummary]


class HistoryFieldScore(BaseModel):
    field: str
    score: int
    reasoning: str


class HistoryEvaluation(BaseModel):
    overall_score: float
    scores: list[HistoryFieldScore]
    critical_errors: list[str]
    judge_confidence: Confianca


class HistoryClassification(BaseModel):
    id: int | str
    assunto: str | None
    mensagem: str
    tipo_solicitacao: TipoSolicitacao
    area_sugerida: AreaSugerida
    proxima_acao: ProximaAcao
    confianca: Confianca
    urgencia: Urgencia
    empresa: str | None
    cnpj: str | None
    documentos_identificados: list[str]
    data_mencionada: str | None
    justificativa: str
    latency_ms: int
    evaluation: HistoryEvaluation | None


class HistoryDetail(BaseModel):
    run_id: str
    timestamp: str | None
    model: str | None
    prompt_version: str | None
    evaluated: bool
    classifications: list[HistoryClassification]


@lru_cache
def get_classifier() -> TriageClassifier:
    """Cached classifier singleton (overridden in tests)."""
    return TriageClassifier(get_settings())


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, log_dir=settings.storage_path / "logs")

    app = FastAPI(
        title="Message Triage Agent",
        description="Structured LLM-based triage for business (PJ) messages.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _generic_handler(request: Request, exc: Exception):
        trace_id = uuid.uuid4().hex
        log.error("api.unhandled_error", trace_id=trace_id, error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "trace_id": trace_id},
        )

    # --- classification ----------------------------------------------------

    def _persist(pairs: list[tuple[TriageInput, TriageOutput]], settings: Settings) -> None:
        results = [
            ClassificationResult(
                input=inp,
                output=out,
                latency_ms=int(out.metadata.get("latency_ms", 0)),
                retry_count=int(out.metadata.get("retry_count", 0)),
            )
            for inp, out in pairs
        ]
        total_fallback = sum(1 for _, o in pairs if o.metadata.get("fallback"))
        run = RunRecord(
            run_id=uuid.uuid4().hex,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "model": settings.classifier_model,
                "provider": settings.classifier_provider,
                "prompt_version": PROMPT_VERSION,
                "total_inputs": len(pairs),
                "total_success": len(pairs) - total_fallback,
                "total_fallback": total_fallback,
            },
            results=results,
        )
        save_run(run)

    @app.post("/triage", response_model=TriageOutput, tags=["classification"])
    def triage(inp: TriageInput, classifier: TriageClassifier = Depends(get_classifier)):
        out = classifier.classify(inp)
        _persist([(inp, out)], settings)
        return out

    @app.post("/triage/batch", response_model=list[TriageOutput], tags=["classification"])
    def triage_batch(
        inputs: list[TriageInput],
        classifier: TriageClassifier = Depends(get_classifier),
    ):
        pairs = [(inp, classifier.classify(inp)) for inp in inputs]
        _persist(pairs, settings)
        return [out for _, out in pairs]

    @app.get("/health", tags=["ops"])
    def health():
        return {
            "status": "ok",
            "provider": settings.classifier_provider,
            "model": settings.classifier_model,
            "prompt_version": PROMPT_VERSION,
        }

    @app.get("/logs", tags=["ops"])
    def logs(limit: int = 100):
        """Tail the persisted structured event log (most recent first).

        Reads today's JSONL sink. Content is LGPD-safe by construction — the log
        never contains raw message bodies, only ids, lengths, stages and timing.
        """
        path = current_log_file()
        if path is None or not path.exists():
            return {"total": 0, "items": []}
        lines = path.read_text(encoding="utf-8").splitlines()
        tail = lines[-limit:] if limit > 0 else lines
        items = []
        for line in reversed(tail):
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return {"total": len(lines), "items": items}

    # --- dashboard (read-only) --------------------------------------------

    @app.get("/runs", tags=["dashboard"])
    def get_runs(limit: int = 50, offset: int = 0):
        evals_by_run = {ev.run_id: ev for ev in list_evaluations()}
        runs = list(reversed(list_runs()))
        page = runs[offset : offset + limit]
        summaries = []
        for r in page:
            ev = evals_by_run.get(r.run_id)
            mean_score = (
                round(sum(t.overall_score for t in ev.evaluations) / len(ev.evaluations), 3)
                if ev and ev.evaluations
                else None
            )
            summaries.append(
                {
                    "run_id": r.run_id,
                    "timestamp": r.metadata.get("timestamp"),
                    "model": r.metadata.get("model"),
                    "prompt_version": r.metadata.get("prompt_version"),
                    "total_classifications": len(r.results),
                    "mean_score": mean_score,
                }
            )
        return {"total": len(runs), "items": summaries}

    @app.get("/metrics", tags=["dashboard"])
    def metrics():
        return aggregate_all(list_evaluations(), list_runs())

    @app.get("/metrics/timeline", tags=["dashboard"])
    def timeline(granularity: str = "day"):
        return [
            {"timestamp": ts.isoformat(), "score": score}
            for ts, score in score_trend(list_evaluations(), granularity)
        ]

    # --- history (storage-agnostic view) ----------------------------------

    @app.get("/history", response_model=HistoryPage, tags=["history"])
    def history():
        evals_by_run = {ev.run_id: ev for ev in list_evaluations()}
        runs = list(reversed(list_runs()))
        items = []
        for r in runs:
            ev = evals_by_run.get(r.run_id)
            mean_score = (
                round(sum(t.overall_score for t in ev.evaluations) / len(ev.evaluations), 3)
                if ev and ev.evaluations
                else None
            )
            items.append(
                HistorySummary(
                    run_id=r.run_id,
                    timestamp=r.metadata.get("timestamp"),
                    model=r.metadata.get("model"),
                    prompt_version=r.metadata.get("prompt_version"),
                    total_classifications=len(r.results),
                    mean_score=mean_score,
                    evaluated=ev is not None,
                )
            )
        return HistoryPage(total=len(items), items=items)

    @app.get("/history/{run_id}", response_model=HistoryDetail, tags=["history"])
    def history_detail(run_id: str):
        from evaluation.storage import load_run

        try:
            run = load_run(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

        ev = next((e for e in list_evaluations() if e.run_id == run_id), None)
        eval_by_input = {str(e.input_id): e for e in (ev.evaluations if ev else [])}

        classifications = []
        for res in run.results:
            out = res.output
            te = eval_by_input.get(str(out.id))
            evaluation = (
                HistoryEvaluation(
                    overall_score=te.overall_score,
                    scores=[
                        HistoryFieldScore(field=s.field, score=s.score, reasoning=s.reasoning)
                        for s in te.scores
                    ],
                    critical_errors=te.critical_errors,
                    judge_confidence=te.judge_confidence,
                )
                if te
                else None
            )
            classifications.append(
                HistoryClassification(
                    id=out.id,
                    assunto=res.input.assunto,
                    mensagem=res.input.mensagem,
                    tipo_solicitacao=out.tipo_solicitacao,
                    area_sugerida=out.area_sugerida,
                    proxima_acao=out.proxima_acao,
                    confianca=out.confianca,
                    urgencia=out.urgencia,
                    empresa=out.empresa,
                    cnpj=out.cnpj,
                    documentos_identificados=out.documentos_identificados,
                    data_mencionada=out.data_mencionada,
                    justificativa=out.justificativa,
                    latency_ms=res.latency_ms,
                    evaluation=evaluation,
                )
            )

        return HistoryDetail(
            run_id=run.run_id,
            timestamp=run.metadata.get("timestamp"),
            model=run.metadata.get("model"),
            prompt_version=run.metadata.get("prompt_version"),
            evaluated=ev is not None,
            classifications=classifications,
        )

    # --- reports (offline evaluation) -------------------------------------

    @app.get("/reports/pending", tags=["reports"])
    def pending_reports():
        """Runs that have no evaluation yet — candidates for a report run."""
        from evaluation.run_evaluation import _pending_runs

        pending = _pending_runs()
        return {
            "pending": len(pending),
            "run_ids": [r.run_id for r in pending],
        }

    @app.post("/reports/run", tags=["reports"])
    def run_reports(payload: RunReportsRequest, background_tasks: BackgroundTasks):
        """Run the LLM judge over pending runs and regenerate the aggregate in the background."""
        global REPORT_TASK_STATUS
        if REPORT_TASK_STATUS["status"] == "running":
            raise HTTPException(status_code=400, detail="Evaluation is already running in the background.")

        # Set status to running initially so immediate calls know it started
        REPORT_TASK_STATUS["status"] = "running"
        REPORT_TASK_STATUS["progress"] = 0
        REPORT_TASK_STATUS["total"] = 0
        REPORT_TASK_STATUS["error"] = None
        REPORT_TASK_STATUS["result"] = None

        background_tasks.add_task(background_run_reports, payload.limit, settings)
        return {"status": "running", "message": "Evaluation started in the background."}

    @app.get("/reports/status", tags=["reports"])
    def reports_status():
        """Check the status of the background evaluation task."""
        global REPORT_TASK_STATUS
        return REPORT_TASK_STATUS

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
