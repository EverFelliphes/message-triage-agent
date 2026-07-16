from datetime import datetime, timedelta

from evaluation.aggregator import aggregate_all, compare_versions, detect_regression
from evaluation.rubric import FieldScore, TriageEvaluation, compute_overall
from evaluation.storage import ClassificationResult, EvaluationRecord, RunRecord
from triage.schemas import TriageInput, TriageOutput


def _output(input_id, tipo="interesse_em_credito_pj", conf="alto", model="claude-sonnet-5"):
    return TriageOutput(
        id=input_id,
        tipo_solicitacao=tipo,
        area_sugerida="comercial",
        proxima_acao="encaminhar_comercial",
        confianca=conf,
        urgencia="baixa",
        justificativa="Justificativa suficientemente longa para a validação do schema.",
        metadata={
            "prompt_version": "v1",
            "model_name": model,
            "fallback": False,
            "latency_ms": 120,
        },
    )


def _run(run_id, input_ids):
    results = [
        ClassificationResult(
            input=TriageInput(id=i, mensagem="mensagem de teste"),
            output=_output(i),
            latency_ms=100 + i,
            retry_count=0,
        )
        for i in input_ids
    ]
    return RunRecord(run_id=run_id, metadata={"model": "claude-sonnet-5"}, results=results)


def _scores(value):
    return [
        FieldScore(field=f, score=value, reasoning="ok")
        for f in ("tipo_solicitacao", "entidades", "proxima_acao", "confianca", "justificativa")
    ]


def _eval(eval_id, run_id, input_ids, value, ts=None):
    evs = [
        TriageEvaluation(
            input_id=i,
            scores=_scores(value),
            overall_score=compute_overall(_scores(value)),
            critical_errors=[],
            judge_confidence="alto",
        )
        for i in input_ids
    ]
    return EvaluationRecord(
        eval_id=eval_id,
        run_id=run_id,
        judge_model="gpt-4-turbo",
        evaluations=evs,
        timestamp=ts or datetime.now(),
    )


def test_compute_overall_weighted_mean():
    assert compute_overall(_scores(5)) == 5.0
    assert compute_overall(_scores(3)) == 3.0


def test_aggregate_all_basic():
    runs = [_run("r1", [1, 2]), _run("r2", [3, 4])]
    evals = [_eval("e1", "r1", [1, 2], 5), _eval("e2", "r2", [3, 4], 3)]
    m = aggregate_all(evals, runs)
    assert m.total_runs == 2
    assert m.total_classifications == 4
    assert m.total_evaluations == 2
    assert m.mean_overall_score == 4.0
    assert m.category_distribution["interesse_em_credito_pj"] == 4
    assert m.p50_latency_ms > 0


def test_empty_returns_zeroed_metrics():
    m = aggregate_all([], [])
    assert m.total_runs == 0
    assert m.mean_overall_score == 0.0


def test_detect_regression_flags_drop():
    base = [_eval("e1", "r1", [1, 2], 5, ts=datetime.now() - timedelta(days=1))]
    current = _eval("e2", "r2", [3, 4], 2, ts=datetime.now())
    report = detect_regression(current, base + [current], threshold=0.5)
    assert report.regressed is True
    assert report.delta < 0


def test_detect_regression_no_drop():
    base = [_eval("e1", "r1", [1, 2], 5, ts=datetime.now() - timedelta(days=1))]
    current = _eval("e2", "r2", [3, 4], 5, ts=datetime.now())
    report = detect_regression(current, base + [current])
    assert report.regressed is False


def test_compare_versions():
    runs = [_run("r1", [1, 2])]
    evals = [_eval("e1", "r1", [1, 2], 4)]
    result = compare_versions(evals, runs, key="prompt_version")
    assert result["v1"] == 4.0
