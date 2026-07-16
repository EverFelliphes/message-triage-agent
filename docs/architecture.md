# Architecture

## Overview

The system is a layered pipeline. A message flows through deterministic extractors and a single LLM call in parallel, is merged (rules win on regulated fields), reinforced (low confidence → human), validated against a strict contract, and persisted as a versioned artifact. An offline evaluation pipeline judges those artifacts and feeds a dashboard.

```
Input → [Extractors] ┐
                     ├→ [Merge] → [Reinforcement] → [Validation] → [Storage] → [Judge] → [Aggregate] → [Dashboard]
Input → [Classifier] ┘
```

## Design principles

1. **Rule/AI separation is physical.** Deterministic logic ([`extractors.py`](../backend/src/triage/extractors.py)) lives in a different module from the LLM call ([`classifier.py`](../backend/src/triage/classifier.py)). The merge layer lets rules *override* the model on regulated fields (CNPJ, urgency).
2. **One prompt, one response.** A single LLM call returns the whole structured decision. No chains, no agent loop.
3. **Fail-safe defaults.** Malformed output self-heals via a correction prompt; exhausting retries yields a deterministic "route to a human" fallback. Low confidence always routes to manual review.
4. **Filesystem storage.** Versioned JSON artifacts, each carrying `schema_version`, behind a small I/O interface.
5. **Provider-agnostic model access.** The classifier depends on an `LLMProvider` Protocol, never an SDK directly.

## Layer by layer

- **Extractors** — regex + CNPJ check-digit (modulo 11) validation, BR/relative date parsing, urgency keywords. Pure functions, no LLM, fully unit-tested. This is the audit evidence of rule/AI separation.
- **Prompts** ([`prompts.py`](../backend/src/triage/prompts.py)) — persona + full taxonomy + decision matrix + few-shot examples ordered least-to-most, no CoT. See [prompt_engineering.md](prompt_engineering.md).
- **Provider** ([`providers.py`](../backend/src/triage/providers.py)) — `LLMProvider` Protocol + adapters. Includes a decorator `retry_on_transient_error` with exponential backoff and random jitter to handle transient API errors (like 503 Service Unavailable or 429 Rate Limit) automatically across all providers.
- **Classifier** — orchestrates extractors → prompt → provider call (retry/self-heal) → merge → reinforcement → metadata. Includes a robust substring scanner `_extract_json` that matches curly braces from largest to smallest to isolate and parse the valid JSON object, prioritizing relevant taxonomy keys.
- **Storage** ([`storage.py`](../backend/evaluation/storage.py)) — `RunRecord`/`EvaluationRecord` I/O; versioned filenames.
- **Evaluation** — rubric, cross-family judge, aggregator, reporter, CLI runner.
- **API** ([`api.py`](../backend/src/triage/api.py)) — classification endpoints + dashboard data endpoints. Features asynchronous report processing offloaded to FastAPI `BackgroundTasks` (`POST /reports/run`) and a status query endpoint (`GET /reports/status`) to enable progress pooling on the frontend and prevent gateway timeouts.
- **Frontend** — a typed view over the same storage the eval pipeline writes to.

## Model portability — provider abstraction

**Chosen:** a thin `LLMProvider` Protocol with per-SDK adapters selected by `settings.classifier_provider`. Swapping Claude → Gemini is a config change; the classifier and prompts are untouched. This mirrors the storage layer's isolated interface and adds zero framework dependency, keeping the classifier auditable and unit-testable against a fake provider.

**Valid model ids per provider** (set in `.env`; swap by config alone):

| Role | Provider | Recommended | Alternatives |
|---|---|---|---|
| Classifier | anthropic | `claude-sonnet-5` (best value) | `claude-opus-4-8` (max accuracy) · `claude-haiku-4-5` (cheapest) |
| Classifier | gemini | `gemini-2.5-pro` | `gemini-2.5-flash` · `gemini-2.0-flash` |
| Judge | openai | `gpt-4o` | `gpt-4.1` · `gpt-4-turbo` |
| Judge | gemini | `gemini-2.5-pro` | `gemini-2.5-flash` |

The classifier defaults to Sonnet 5 — a triage classifier is high-volume, and Sonnet 5 lands near Opus accuracy at a fraction of the output cost; bump to Opus 4.8 when accuracy outweighs cost. Keep the judge in a **different family** than the classifier (cross-family bias mitigation). Anthropic ids are current as of this writing; OpenAI/Gemini ids evolve — verify against each provider's model list before deploying.

**Alternatives considered** (and when each would win):

- **Pydantic AI** — model-agnostic, structured-output-native; the natural pick for a Pydantic-first codebase if we wanted typed outputs + provider switching without hand-writing adapters.
- **Instructor** — patches the provider client to return validated Pydantic models with built-in retry (overlaps our correction loop); multi-provider via LiteLLM.
- **LiteLLM** — thinnest routing layer, ~100 providers behind one call, plus proxy/fallback/cost tracking. Wins with many providers or dynamic routing.
- **LangChain** — full orchestration framework. Rejected here (below), but the right tool once the pipeline grows chains, tools, or agents.

## Techniques rejected

- **LangChain** — abstractions we don't need for a single call, at the cost of auditability.
- **Classical RAG** — the taxonomy is small and fixed; it fits in the system prompt.
- **BERT fine-tuning** — no labeled dataset; and RA-ICL can match fine-tuned encoders on intent classification (Khrapunova 2025).
- **Full constrained decoding** — the "constraint tax": reasoning degrades with format rigor (Tam et al. 2024). We use Format-Restricting Instructions + retry instead.
- **Chain-of-Thought in classification** — didn't help empirically (Khrapunova 2025). CoT is reserved for the judge.
- **Runtime LLM-as-Judge** — redundant with the deterministic safeguards and adds latency; evaluation is offline.
- **Self-consistency** — `temperature=0` makes sampling-based voting moot.
- **Database** — over-dimensioned for dozens of records; JSON artifacts are git-diffable audit evidence.

## LGPD / PII

Messages carry business PII (CNPJ, company names). The system never logs raw message content — structured logs emit only ids, trace ids, lengths, and timing. Artifacts persist the message (needed for auditability and evaluation) on the local filesystem behind the storage interface; a production deployment would add retention limits and access control at that boundary.

## Next steps (with quantitative triggers)

- **CI pipeline** (lint/tests/docker build) once the repo has collaborators or merge traffic.
- **Human-labeled gold set** (~20–50 to start) to report real accuracy and validate the judge itself.
- **RA-ICL** when ~500–1000 reviewed classifications are available.
- **Fine-tuned encoder** when volume/latency justify the training + serving cost.
- **Conditional LLM-as-Judge** for medium-confidence cases in production.
- **Storage migration** to an event log / warehouse when concurrent writers or analytical queries emerge — isolated to the storage interface.

## References

Khrapunova 2025; Vatsal & Dubey 2024; Tam et al. 2024; Zheng et al. 2023 — see the [root README](../README.md#references).
