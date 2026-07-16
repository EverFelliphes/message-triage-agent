"""Evaluation runner (BE-13).

Orchestrates the full offline evaluation cycle: judge unevaluated runs, persist
evaluation records + individual reports, then always regenerate the aggregate
report. Exposed both as a CLI and as importable functions (``run_evaluations``,
``resolve_targets``) so the API can trigger the same cycle on demand.

CLI usage:

    python -m evaluation.run_evaluation --all-pending
    python -m evaluation.run_evaluation --run-id <id>
    python -m evaluation.run_evaluation --aggregate-only
"""

from __future__ import annotations

import argparse
import uuid

from rich.console import Console

from triage.config import Settings, get_settings

from .aggregator import aggregate_all, detect_regression
from .judge import LLMJudge
from .reporter import generate_aggregate_report, generate_individual_report
from .storage import (
    EvaluationRecord,
    RunRecord,
    list_evaluations,
    list_runs,
    load_run,
    save_evaluation,
)

console = Console()


def _pending_runs() -> list[RunRecord]:
    evaluated = {ev.run_id for ev in list_evaluations()}
    return [r for r in list_runs() if r.run_id not in evaluated]


def resolve_targets(*, run_id: str | None = None, limit: int | None = None) -> list[RunRecord]:
    """Pick the runs to evaluate: a specific run, or the pending ones.

    ``limit`` keeps only the ``N`` most recent pending runs (``list_runs`` is
    chronological); ``None`` means *all* pending runs.
    """
    if run_id:
        return [load_run(run_id)]
    targets = _pending_runs()
    if limit is not None:
        targets = targets[-limit:] if limit > 0 else []
    return targets


def _evaluate_run(run: RunRecord, judge: LLMJudge) -> EvaluationRecord:
    evaluations = [judge.evaluate(res.input, res.output) for res in run.results]
    record = EvaluationRecord(
        eval_id=uuid.uuid4().hex,
        run_id=run.run_id,
        judge_model=judge.judge_model,
        evaluations=evaluations,
    )
    save_evaluation(record)
    generate_individual_report(run, record)
    return record


def run_evaluations(settings: Settings, targets: list[RunRecord]) -> tuple[list[dict], object]:
    """Judge each target run, persist artifacts, regenerate the aggregate report.

    Returns ``(per_run_results, aggregate_metrics)``. Always refreshes the
    aggregate — even when ``targets`` is empty — so callers get current metrics.
    """
    results: list[dict] = []
    if targets:
        judge = LLMJudge(settings)
        for run in targets:
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
    metrics = aggregate_all(list_evaluations(), list_runs())
    generate_aggregate_report(metrics)
    return results, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the offline evaluation cycle.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-id", help="Evaluate a specific run.")
    group.add_argument("--all-pending", action="store_true", help="Evaluate all unevaluated runs.")
    group.add_argument(
        "--aggregate-only", action="store_true", help="Only regenerate the aggregate report."
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.aggregate_only:
        metrics = aggregate_all(list_evaluations(), list_runs())
        generate_aggregate_report(metrics)
    else:  # default + --all-pending + --run-id
        targets = resolve_targets(run_id=args.run_id)
        if not targets:
            console.print("[yellow]No pending runs to evaluate.[/yellow]")
        else:
            for run in targets:
                console.print(
                    f"[cyan]Evaluating[/cyan] {run.run_id} ({len(run.results)} items)…"
                )
        results, metrics = run_evaluations(settings, targets)
        for r in results:
            colour = "red" if r["regressed"] else "green"
            console.print(
                f"  {r['run_id']}: score [bold]{r['score']:.2f}[/bold] "
                f"([{colour}]diff {r['delta']:+.2f}[/{colour}] "
                f"vs baseline {r['baseline_score']:.2f})"
            )

    console.print(
        f"[green]Aggregate updated[/green] — mean score "
        f"[bold]{metrics.mean_overall_score:.2f}[/bold] over {metrics.total_evaluations} evals."
    )


if __name__ == "__main__":
    main()
