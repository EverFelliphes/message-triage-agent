"""End-to-end examples runner (BE-17).

Reads examples/inputs.json, classifies each through TriageClassifier (in-process,
not via HTTP), persists one RunRecord, and prints a rich summary. This produces the
real ``storage/runs/*.json`` artifact used as evidence and by the dashboard.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Allow ``python scripts/run_examples.py`` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluation.storage import ClassificationResult, RunRecord, save_run  # noqa: E402
from triage.classifier import TriageClassifier  # noqa: E402
from triage.config import get_settings  # noqa: E402
from triage.logging_setup import configure_logging  # noqa: E402
from triage.prompts import PROMPT_VERSION  # noqa: E402
from triage.schemas import TriageInput  # noqa: E402

console = Console()
_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "inputs.json"


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    import math

    return float(ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)])


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    inputs = [TriageInput.model_validate(x) for x in json.loads(_EXAMPLES.read_text("utf-8"))]

    classifier = TriageClassifier(settings)
    results: list[ClassificationResult] = []
    table = Table(title="Triage results")
    for col in ("id", "tipo", "próxima ação", "confiança", "urgência", "latency (ms)"):
        table.add_column(col)

    for inp in inputs:
        out = classifier.classify(inp)
        latency = int(out.metadata.get("latency_ms", 0))
        results.append(
            ClassificationResult(
                input=inp,
                output=out,
                latency_ms=latency,
                retry_count=int(out.metadata.get("retry_count", 0)),
            )
        )
        style = "yellow" if out.confianca.value == "baixo" else None
        table.add_row(
            str(inp.id),
            out.tipo_solicitacao.value,
            out.proxima_acao.value,
            out.confianca.value,
            out.urgencia.value,
            str(latency),
            style=style,
        )

    total_fallback = sum(1 for r in results if r.output.metadata.get("fallback"))
    run = RunRecord(
        run_id=uuid.uuid4().hex,
        metadata={
            "timestamp": datetime.now().isoformat(),
            "model": settings.classifier_model,
            "provider": settings.classifier_provider,
            "prompt_version": PROMPT_VERSION,
            "total_inputs": len(results),
            "total_success": len(results) - total_fallback,
            "total_fallback": total_fallback,
        },
        results=results,
    )
    path = save_run(run)

    console.print(table)
    latencies = [r.latency_ms for r in results]
    dist: dict[str, int] = {}
    for r in results:
        dist[r.output.tipo_solicitacao.value] = dist.get(r.output.tipo_solicitacao.value, 0) + 1
    console.print(f"\n[bold]Distribution:[/bold] {dist}")
    console.print(
        f"[bold]Latency:[/bold] p50={_percentile(latencies, 50):.0f}ms "
        f"p95={_percentile(latencies, 95):.0f}ms  "
        f"[bold]Fallbacks:[/bold] {total_fallback}/{len(results)}"
    )
    console.print(f"[green]Saved run →[/green] {path}")


if __name__ == "__main__":
    main()
