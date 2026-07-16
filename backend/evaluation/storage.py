"""Filesystem storage layer (BE-08).

Versioned JSON artifacts for runs and evaluations — the shared substrate for the
evaluation pipeline and the dashboard. Every file carries ``schema_version`` for
forward compatibility. Pure I/O; no business logic.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from triage.config import get_settings
from triage.schemas import TriageInput, TriageOutput

from .rubric import TriageEvaluation

SCHEMA_VERSION = "1.0"


class ClassificationResult(BaseModel):
    input: TriageInput
    output: TriageOutput
    latency_ms: int
    retry_count: int


class RunRecord(BaseModel):
    run_id: str
    schema_version: str = SCHEMA_VERSION
    metadata: dict = Field(default_factory=dict)
    results: list[ClassificationResult] = Field(default_factory=list)


class EvaluationRecord(BaseModel):
    eval_id: str
    run_id: str
    judge_model: str
    schema_version: str = SCHEMA_VERSION
    evaluations: list[TriageEvaluation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# --- paths -----------------------------------------------------------------


def _runs_dir() -> Path:
    p = get_settings().storage_path / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _evals_dir() -> Path:
    p = get_settings().storage_path / "evaluations"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text).strip("-").lower()


def _write_json(path: Path, model: BaseModel) -> Path:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return path


# --- runs ------------------------------------------------------------------


def save_run(run: RunRecord) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    commit = str(run.metadata.get("git_commit", "nogit"))[:7]
    return _write_json(_runs_dir() / f"run_{ts}_{commit}.json", run)


def load_run(run_id: str) -> RunRecord:
    for path in _runs_dir().glob("run_*.json"):
        rec = RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if rec.run_id == run_id:
            return rec
    raise FileNotFoundError(f"run not found: {run_id}")


def list_runs(since: date | None = None) -> list[RunRecord]:
    runs: list[RunRecord] = []
    for path in sorted(_runs_dir().glob("run_*.json")):
        rec = RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if since is not None:
            ts = rec.metadata.get("timestamp")
            if ts and datetime.fromisoformat(ts).date() < since:
                continue
        runs.append(rec)
    return runs


# --- evaluations -----------------------------------------------------------


def save_evaluation(evaluation: EvaluationRecord) -> Path:
    ts = evaluation.timestamp.strftime("%Y-%m-%d_%H%M%S")
    name = f"eval_{ts}_{_slug(evaluation.judge_model)}.json"
    return _write_json(_evals_dir() / name, evaluation)


def load_evaluation(eval_id: str) -> EvaluationRecord:
    for path in _evals_dir().glob("eval_*.json"):
        rec = EvaluationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if rec.eval_id == eval_id:
            return rec
    raise FileNotFoundError(f"evaluation not found: {eval_id}")


def list_evaluations(
    since: date | None = None, judge_model: str | None = None
) -> list[EvaluationRecord]:
    evals: list[EvaluationRecord] = []
    for path in sorted(_evals_dir().glob("eval_*.json")):
        rec = EvaluationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if since is not None and rec.timestamp.date() < since:
            continue
        if judge_model is not None and rec.judge_model != judge_model:
            continue
        evals.append(rec)
    return evals


def load_all_evaluations() -> list[EvaluationRecord]:
    return list_evaluations()
