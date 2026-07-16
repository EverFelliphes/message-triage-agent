# Prompt Engineering

The prompt is the highest-leverage part of the system. Every choice below is empirical, not aesthetic. Implementation: [`prompts.py`](../backend/src/triage/prompts.py).

## Structure

`system` (persona + taxonomy + decision matrix + output format) followed by hand-picked few-shot pairs, then the target message. The system prompt is passed separately from the message list, per the SDK contract.

Excerpt:

> Você é um analista de triagem em uma instituição financeira brasileira, especializado em identificar solicitações de clientes PJ. […] 1. Classifique primeiro. 2. Justifique depois, citando o trecho da mensagem. […] Responda SOMENTE com um objeto JSON válido.

## Design choices

| Choice | Why | Source |
|---|---|---|
| **Persona prompting** | Grounds the model in the PJ-analyst role and vocabulary | Vatsal & Dubey 2024 |
| **Few-shot, 4 hand-picked examples** | Cover the ambiguous pairs (docs vs. pendência; cadastral vs. crédito), out-of-scope, and a poorly-formatted CNPJ | Khrapunova 2025 |
| **Static least-to-most ordering** | Most representative example sits last, nearest the query, exploiting recency bias | Zhao et al. 2021; Khrapunova 2025 |
| **No CoT in examples** | CoT did not improve classification empirically; it adds tokens and latency | Khrapunova 2025 |
| **Classify-then-justify** | Forces the decision before the rationalization, reducing post-hoc justification | — |
| **Temperature 0** | Determinism and reproducibility for an auditable decision | — |

## FRI vs. constrained decoding

We use **Format-Restricting Instructions** (ask for JSON in a specified shape) plus a strict Pydantic validation + retry loop, rather than full constrained/grammar decoding. Tam et al. (2024) document a "constraint tax": the more rigidly you force the output format at decode time, the more reasoning degrades. FRI keeps the model's reasoning intact and moves format enforcement to a cheap validate-and-retry step.

## Retry and self-healing

On a JSON or schema-validation failure the classifier re-prompts with the previous (bad) answer and the specific error, asking for a corrected JSON — a lightweight verify-then-fix loop. After `max_retries` it returns a deterministic fallback (low confidence → manual review) rather than crashing.
Additionally, we use a robust substring scanner `extract_json_object` to parse valid JSON objects from conversational output. The default generation token limit is set to `max_tokens=4096` to prevent truncation on large JSON structures containing detailed step-by-step reasoning (CoT) during evaluation.

## Deterministic merge

Extractors run before the model and override it on regulated fields: a valid extracted CNPJ replaces the model's, and a high-urgency keyword overrides a low-urgency model call. The model is never the sole authority on a field a rule can verify.

## Prompt versioning

`PROMPT_VERSION` is stamped into every output's metadata and stored with each run, so the aggregator can compare versions over time. In production this enables A/B and shadow testing: run `PROMPT_V2` on a traffic slice, compare judge scores per version before promoting.

## References

Khrapunova 2025; Vatsal & Dubey 2024; Zhao et al. 2021; Tam et al. 2024 — see the [root README](../README.md#references).
