"""Cross-run aggregation (BE-11).

Pure functions that turn stored runs + evaluations into historical metrics for the
dashboard and reports. No I/O. Over a tiny corpus these numbers are indicative,
not statistically robust — the module exists as the infrastructure for when volume
arrives (see docs/evaluation.md).
"""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, Field

from .rubric import MAX_SCORE, RUBRIC
from .storage import EvaluationRecord, RunRecord

_CONF_BUCKETS = ["baixo", "medio", "alto"]


class _JoinedRecord(BaseModel):
    """One classification joined with its judge evaluation."""

    timestamp: datetime
    input_id: int | str
    tipo: str
    confianca: str
    overall: float
    field_scores: dict[str, int]
    critical_errors: list[str]
    latency_ms: int
    retry_count: int
    fallback: bool
    prompt_version: str
    model_name: str


class AggregateMetrics(BaseModel):
    total_runs: int = 0
    total_classifications: int = 0
    total_evaluations: int = 0
    time_range: tuple[datetime, datetime] | None = None

    mean_overall_score: float = 0.0
    score_trend: list[tuple[datetime, float]] = Field(default_factory=list)
    score_per_field_over_time: dict[str, list[tuple[datetime, float]]] = Field(default_factory=dict)

    mean_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    fallback_rate: float = 0.0
    retry_rate: float = 0.0

    confidence_calibration_matrix: dict = Field(default_factory=dict)
    calibration_score: float = 0.0

    category_distribution: dict[str, int] = Field(default_factory=dict)
    per_category_mean_score: dict[str, float] = Field(default_factory=dict)
    critical_error_count_per_category: dict[str, int] = Field(default_factory=dict)

    prompt_version_performance: dict[str, float] = Field(default_factory=dict)
    model_performance: dict[str, float] = Field(default_factory=dict)


class RegressionReport(BaseModel):
    regressed: bool
    current_score: float
    baseline_score: float
    delta: float
    message: str


# --- helpers ---------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return float(ordered[rank])


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _join(evaluations: list[EvaluationRecord], runs: list[RunRecord]) -> list[_JoinedRecord]:
    """Join judge evaluations with their classification outputs by run + input id."""
    runs_by_id = {r.run_id: r for r in runs}
    joined: list[_JoinedRecord] = []
    for ev in evaluations:
        run = runs_by_id.get(ev.run_id)
        if run is None:
            continue
        results_by_id = {str(res.input.id): res for res in run.results}
        for te in ev.evaluations:
            res = results_by_id.get(str(te.input_id))
            if res is None:
                continue
            meta = res.output.metadata
            joined.append(
                _JoinedRecord(
                    timestamp=ev.timestamp,
                    input_id=te.input_id,
                    tipo=res.output.tipo_solicitacao.value,
                    confianca=res.output.confianca.value,
                    overall=te.overall_score,
                    field_scores={s.field: s.score for s in te.scores},
                    critical_errors=te.critical_errors,
                    latency_ms=res.latency_ms,
                    retry_count=res.retry_count,
                    fallback=bool(meta.get("fallback", False)),
                    prompt_version=str(meta.get("prompt_version", "unknown")),
                    model_name=str(meta.get("model_name", "unknown")),
                )
            )
    return joined


def _group_mean(pairs: list[tuple[str, float]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for key, value in pairs:
        buckets.setdefault(key, []).append(value)
    return {k: _mean(v) for k, v in buckets.items()}


# --- public API ------------------------------------------------------------


def score_trend(
    evaluations: list[EvaluationRecord], granularity: str = "day"
) -> list[tuple[datetime, float]]:
    """Mean overall score per evaluation record, chronologically."""
    ordered = sorted(evaluations, key=lambda e: e.timestamp)
    trend: list[tuple[datetime, float]] = []
    for ev in ordered:
        scores = [te.overall_score for te in ev.evaluations]
        if scores:
            trend.append((ev.timestamp, _mean(scores)))
    return trend


def compare_versions(
    evaluations: list[EvaluationRecord],
    runs: list[RunRecord],
    key: str = "prompt_version",
) -> dict[str, float]:
    """Mean overall score grouped by prompt_version or model_name."""
    joined = _join(evaluations, runs)
    pairs = [(getattr(j, key), j.overall) for j in joined]
    return _group_mean(pairs)


def detect_regression(
    current_run: EvaluationRecord,
    historical: list[EvaluationRecord],
    threshold: float = 1.0,
) -> RegressionReport:
    """Flag a regression when the current mean drops more than ``threshold``.

    ``threshold`` is on the 1-``MAX_SCORE`` scale (default 1.0 point).
    """
    current = _mean([te.overall_score for te in current_run.evaluations])
    past_scores = [
        te.overall_score
        for ev in historical
        if ev.eval_id != current_run.eval_id
        for te in ev.evaluations
    ]
    baseline = _mean(past_scores)
    delta = round(current - baseline, 4)
    regressed = baseline > 0 and (baseline - current) > threshold
    msg = (
        f"Regression: score dropped {abs(delta)} vs baseline {baseline}."
        if regressed
        else f"No regression (delta {delta} vs baseline {baseline})."
    )
    return RegressionReport(
        regressed=regressed,
        current_score=current,
        baseline_score=baseline,
        delta=delta,
        message=msg,
    )


def aggregate_all(evaluations: list[EvaluationRecord], runs: list[RunRecord]) -> AggregateMetrics:
    """Compute the full metric set from stored runs + evaluations."""
    joined = _join(evaluations, runs)
    metrics = AggregateMetrics(
        total_runs=len(runs),
        total_classifications=sum(len(r.results) for r in runs),
        total_evaluations=len(evaluations),
    )
    if not joined:
        return metrics

    timestamps = [j.timestamp for j in joined]
    metrics.time_range = (min(timestamps), max(timestamps))
    metrics.mean_overall_score = _mean([j.overall for j in joined])
    metrics.score_trend = score_trend(evaluations)

    # Per-field trend.
    field_over_time: dict[str, list[tuple[datetime, float]]] = {}
    for ev in sorted(evaluations, key=lambda e: e.timestamp):
        for field in RUBRIC:
            vals = [s.score for te in ev.evaluations for s in te.scores if s.field == field]
            if vals:
                field_over_time.setdefault(field, []).append((ev.timestamp, _mean(vals)))
    metrics.score_per_field_over_time = field_over_time

    # System.
    latencies = [float(j.latency_ms) for j in joined]
    metrics.mean_latency_ms = _mean(latencies)
    metrics.p50_latency_ms = _percentile(latencies, 50)
    metrics.p95_latency_ms = _percentile(latencies, 95)
    metrics.fallback_rate = round(sum(j.fallback for j in joined) / len(joined), 4)
    metrics.retry_rate = round(sum(j.retry_count > 0 for j in joined) / len(joined), 4)

    # Distribution.
    for j in joined:
        metrics.category_distribution[j.tipo] = metrics.category_distribution.get(j.tipo, 0) + 1
    metrics.per_category_mean_score = _group_mean([(j.tipo, j.overall) for j in joined])
    for j in joined:
        if j.critical_errors:
            metrics.critical_error_count_per_category[j.tipo] = (
                metrics.critical_error_count_per_category.get(j.tipo, 0) + len(j.critical_errors)
            )

    # Evolution.
    metrics.prompt_version_performance = _group_mean(
        [(j.prompt_version, j.overall) for j in joined]
    )
    metrics.model_performance = _group_mean([(j.model_name, j.overall) for j in joined])

    # Calibration: classifier confidence (rows) x judge overall bucket (cols).
    matrix = {conf: {b: 0 for b in _CONF_BUCKETS} for conf in _CONF_BUCKETS}
    aligned = 0
    # Split the 1..MAX_SCORE range into 3 equal buckets (baixo/medio/alto).
    bucket_width = (MAX_SCORE - 1) / 3
    for j in joined:
        col = _CONF_BUCKETS[min(2, max(0, math.floor((j.overall - 1) / bucket_width)))]
        row = j.confianca if j.confianca in matrix else "medio"
        matrix[row][col] += 1
        if row == col:
            aligned += 1
    metrics.confidence_calibration_matrix = matrix
    metrics.calibration_score = round(aligned / len(joined), 4)

    return metrics
