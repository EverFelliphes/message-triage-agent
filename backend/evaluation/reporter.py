"""Markdown reporting (BE-12).

Human-readable reports for a single run and for the aggregate history. Writes to
``storage/reports/{individual,aggregate}``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from triage.config import get_settings

from .aggregator import AggregateMetrics
from .rubric import MAX_SCORE
from .storage import EvaluationRecord, RunRecord

# Recommend a prompt review when the mean sits below 70% of the scale.
_LOW_SCORE_THRESHOLD = 0.7 * MAX_SCORE


def _reports_dir(kind: str) -> Path:
    p = get_settings().storage_path / "reports" / kind
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_individual_report(run: RunRecord, evaluation: EvaluationRecord) -> str:
    lines = [
        f"# Run report — `{run.run_id}`",
        "",
        f"- Judge model: `{evaluation.judge_model}`",
        f"- Classifications: {len(run.results)}",
        f"- Evaluated: {len(evaluation.evaluations)}",
        "",
        "## Per-classification scores",
        "",
        "| input_id | tipo | confiança | overall | critical errors |",
        "|---|---|---|---|---|",
    ]
    ev_by_id = {str(te.input_id): te for te in evaluation.evaluations}
    for res in run.results:
        te = ev_by_id.get(str(res.input.id))
        overall = f"{te.overall_score:.2f}" if te else "—"
        errs = ", ".join(te.critical_errors) if te and te.critical_errors else "—"
        lines.append(
            f"| {res.input.id} | {res.output.tipo_solicitacao.value} | "
            f"{res.output.confianca.value} | {overall} | {errs} |"
        )
    written = _reports_dir("individual") / f"{run.run_id}.md"
    report = "\n".join(lines) + "\n"
    written.write_text(report, encoding="utf-8")
    return report


def generate_aggregate_report(metrics: AggregateMetrics) -> str:
    lines = [
        "# Aggregate evaluation history",
        "",
        "## Overview",
        f"- Runs: {metrics.total_runs}",
        f"- Classifications: {metrics.total_classifications}",
        f"- Evaluations: {metrics.total_evaluations}",
        f"- Mean overall score: **{metrics.mean_overall_score:.2f}** / {MAX_SCORE}",
        f"- Calibration score: {metrics.calibration_score:.2f}",
        "",
        "## System performance",
        "",
        "| metric | value |",
        "|---|---|",
        f"| mean latency (ms) | {metrics.mean_latency_ms:.0f} |",
        f"| p50 latency (ms) | {metrics.p50_latency_ms:.0f} |",
        f"| p95 latency (ms) | {metrics.p95_latency_ms:.0f} |",
        f"| fallback rate | {metrics.fallback_rate:.0%} |",
        f"| retry rate | {metrics.retry_rate:.0%} |",
        "",
        "## Per-category mean score",
        "",
        "| tipo_solicitacao | count | mean score |",
        "|---|---|---|",
    ]
    for tipo, count in sorted(metrics.category_distribution.items()):
        score = metrics.per_category_mean_score.get(tipo, 0.0)
        lines.append(f"| {tipo} | {count} | {score:.2f} |")

    lines += ["", "## Model performance", "", "| model | mean score |", "|---|---|"]
    for model, score in sorted(metrics.model_performance.items()):
        lines.append(f"| {model} | {score:.2f} |")

    recommendations = _recommendations(metrics)
    if recommendations:
        lines += ["", "## Recommendations", ""]
        lines += [f"- {r}" for r in recommendations]

    report = "\n".join(lines) + "\n"
    out = _reports_dir("aggregate")
    (out / f"history_{date.today().isoformat()}.md").write_text(report, encoding="utf-8")
    (out / "history_latest.md").write_text(report, encoding="utf-8")
    return report


def _recommendations(metrics: AggregateMetrics) -> list[str]:
    recs: list[str] = []
    if metrics.mean_overall_score and metrics.mean_overall_score < _LOW_SCORE_THRESHOLD:
        recs.append(
            f"Mean score below {_LOW_SCORE_THRESHOLD:.1f} — review prompt and few-shot examples."
        )
    if metrics.fallback_rate > 0.1:
        recs.append(
            f"Fallback rate {metrics.fallback_rate:.0%} is high — inspect malformed outputs."
        )
    if metrics.calibration_score and metrics.calibration_score < 0.5:
        recs.append("Low calibration — confidence self-reports are unreliable.")
    for tipo, count in metrics.critical_error_count_per_category.items():
        recs.append(f"{count} critical error(s) concentrated in `{tipo}`.")
    return recs
