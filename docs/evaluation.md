# Evaluation

## What's implemented vs. roadmap

**Implemented:** offline cross-family LLM-as-a-Judge, a weighted rubric, versioned evaluation artifacts, cross-run aggregation (score trend, per-category scores, calibration matrix, latency percentiles, fallback/retry rates, regression detection), Markdown reports, and a live dashboard.

**Roadmap:** human-in-the-loop labeling, a ground-truth gold set, production monitoring with drift detection, and automated CI regression checks.

## Methodology

- **Cross-family judge** (Zheng et al. 2023) — Claude classifies; **GPT-4 or Gemini** evaluates. Cross-family is a deliberate choice to mitigate **self-preference bias** (a model rating its own family higher). The judge reuses the same `LLMProvider` adapters as the classifier. `judge_provider` can be pinned; left unset, it auto-selects a cross-family provider whose key is present (openai → gemini). If only the classifier's family is available it falls back same-family and logs a warning that the mitigation is lost.
- **Weighted rubric** ([`rubric.py`](../backend/evaluation/rubric.py)) — per-field Likert (1–5) with weights summing to 1.0: `tipo_solicitacao` 0.30, `entidades` 0.25, `proxima_acao` 0.20, `confianca` 0.15 (calibration), `justificativa` 0.10. CoT is *enabled* for the judge because scoring is reasoning-heavy.
- **Versioned artifacts** — every run and evaluation is a JSON file with `schema_version`, joinable by `run_id`/`input_id`.
- **Aggregation & regression** ([`aggregator.py`](../backend/evaluation/aggregator.py)) — pure functions over the artifacts; `detect_regression` flags a mean-score drop beyond a threshold vs. the historical baseline.
- **Asynchronous Execution & Polling** — the evaluation runner is offloaded to FastAPI `BackgroundTasks` to process larger runs without causing HTTP gateway timeouts. The frontend performs progress polling and displays a progress bar.

## Known limitations of LLM-as-a-Judge

- **No ground truth.** The score is one model's judgment of another's, not accuracy. This is the single biggest caveat; the gold set on the roadmap addresses it directly.
- **Positional / verbosity bias** — judges can favor longer or first-presented answers.
- **Self-preference bias** — mitigated by cross-family, not eliminated.
- **Small-N.** Over a handful of runs, metrics like p95 latency, regression detection, and per-version performance are *indicative infrastructure*, not statistically robust signal. They exist for when volume arrives.

## Failure-mode analysis

Two views surface systematic issues without ground truth:

- **Calibration matrix** — classifier confidence (rows) × judge score bucket (columns). Off-diagonal mass means the model's self-reported confidence is unreliable — important because the "low confidence → manual review" safeguard depends on it.
- **Per-category error rates** — `critical_error_count_per_category` and `per_category_mean_score` localize where the taxonomy breaks down (usually the ambiguous pairs), pointing directly at which few-shot examples to revise.

## Roadmap triggers

- **Human-in-the-loop:** sample 5–10% of traffic into a feedback UI.
- **Gold set → RA-ICL:** accumulate ~500–1000 reviewed classifications, then retrieve nearest labeled examples per query.
- **Production dashboards:** drift detection on category distribution and score.
- **CI regression checks:** fail a build when `detect_regression` fires against the stored baseline.

## References

Zheng et al. 2023; Khrapunova 2025 — see the [root README](../README.md#references).
