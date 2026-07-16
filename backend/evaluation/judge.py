"""LLM-as-a-Judge (BE-10).

Cross-family evaluation (e.g. Claude classifies, GPT-4 or Gemini judges) following
Zheng et al. 2023, to mitigate self-preference bias. CoT is *enabled* here (unlike
the classifier) because scoring is reasoning-heavy.

The judge reuses the same ``LLMProvider`` abstraction as the classifier (no
duplicated SDK code). The provider is either pinned via ``settings.judge_provider``
or auto-selected: prefer a provider whose key is present and whose family differs
from the classifier's; if none, fall back to the classifier's family and warn that
self-preference bias is no longer mitigated.
"""

from __future__ import annotations

import json
import re

import structlog

from triage.config import (
    _PROVIDER_FAMILY,
    _PROVIDER_KEY_FIELD,
    Settings,
)
from triage.providers import build_provider
from triage.schemas import Confianca, TriageInput, TriageOutput

from .rubric import RUBRIC, FieldScore, TriageEvaluation, compute_overall

log = structlog.get_logger()

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

# Preference order when auto-selecting a judge provider.
_JUDGE_AUTO_ORDER = ("openai", "gemini", "anthropic")
# Sensible default judge model per provider (used only in auto mode).
_DEFAULT_JUDGE_MODEL = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-opus-4-8",
}


def _resolve_judge(settings: Settings) -> tuple[str, str, str]:
    """Return (provider, model, api_key) for the judge.

    Pinned via ``judge_provider`` (uses ``judge_model``), else auto-select a
    cross-family provider whose key is present, else fall back same-family.
    """
    classifier_family = _PROVIDER_FAMILY[settings.classifier_provider.lower()]

    def key_of(provider: str) -> str | None:
        secret = getattr(settings, _PROVIDER_KEY_FIELD[provider])
        return secret.get_secret_value() if secret is not None else None

    if settings.judge_provider is not None:
        provider = settings.judge_provider.lower()
        model = settings.judge_model
    else:
        provider = next(
            (
                p
                for p in _JUDGE_AUTO_ORDER
                if _PROVIDER_FAMILY[p] != classifier_family and key_of(p) is not None
            ),
            settings.classifier_provider.lower(),  # same-family fallback
        )
        model = _DEFAULT_JUDGE_MODEL[provider]

    if _PROVIDER_FAMILY[provider] == classifier_family:
        log.warning(
            "judge.same_family",
            provider=provider,
            note="Judge shares the classifier's model family; self-preference "
            "bias is not mitigated. Provide a cross-family key or set judge_provider.",
        )

    api_key = key_of(provider)
    if api_key is None:
        raise ValueError(
            f"judge provider={provider!r} selected but its API key is missing."
        )
    return provider, model, api_key


def _rubric_text() -> str:
    lines = []
    for field, spec in RUBRIC.items():
        scale = "; ".join(f"{k}={v}" for k, v in spec["scale"].items())
        lines.append(f"- {field} (peso {spec['weight']}): {spec['criterion']} Escala: {scale}")
    return "\n".join(lines)


JUDGE_SYSTEM = """\
Você é um avaliador rigoroso de um sistema de triagem de mensagens PJ. Avalie a
saída do classificador contra a mensagem original usando a rubrica fornecida.
Pense passo a passo antes de pontuar (raciocínio é bem-vindo aqui), mas responda
APENAS com um objeto JSON no formato (score inteiro de 1 a 10):
{
  "scores": [{"field": <str>, "score": <1-10>, "reasoning": <str>}],
  "critical_errors": [<str>],
  "judge_confidence": "alto"|"medio"|"baixo"
}
Inclua exatamente um score por campo da rubrica: tipo_solicitacao, entidades,
proxima_acao, confianca, justificativa.
"""


def extract_json_object(text: str, required_key: str | None = None) -> dict | None:
    """Parse a JSON object from text, prioritizing objects with a required key."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if required_key is None or required_key in data:
                return data
    except json.JSONDecodeError:
        pass

    # Find all occurrences of '{' and '}'
    start_indices = [i for i, char in enumerate(text) if char == '{']
    end_indices = [i for i, char in enumerate(text) if char == '}']

    candidates = []
    # Try all pairs of start and end indices, largest blocks first
    for start in start_indices:
        for end in reversed(end_indices):
            if end > start:
                try:
                    substring = text[start:end+1]
                    data = json.loads(substring)
                    if isinstance(data, dict):
                        if required_key is not None and required_key in data:
                            return data
                        candidates.append(data)
                except json.JSONDecodeError:
                    continue

    if candidates:
        return candidates[0]
    return None


class LLMJudge:
    """Cross-family judge reusing the shared ``LLMProvider`` adapters."""

    def __init__(self, settings: Settings, provider=None) -> None:
        self.settings = settings
        if provider is not None:  # injected fake in tests
            self.provider = provider
        else:
            name, model, api_key = _resolve_judge(settings)
            self.provider = build_provider(name, api_key, model)
        self.judge_model = self.provider.model
        self.provider_name = self.provider.name

    def _complete(self, system: str, user: str) -> str:
        return self.provider.complete(
            system,
            [{"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=self.settings.max_tokens,
        )

    def evaluate(self, inp: TriageInput, output: TriageOutput) -> TriageEvaluation:
        user = (
            f"MENSAGEM ORIGINAL:\nassunto: {inp.assunto}\nmensagem: {inp.mensagem}\n\n"
            f"SAÍDA DO CLASSIFICADOR:\n{output.model_dump_json(indent=2)}\n\n"
            f"RUBRICA:\n{_rubric_text()}"
        )
        for attempt in range(self.settings.max_retries + 1):
            raw = self._complete(JUDGE_SYSTEM, user)
            try:
                data = extract_json_object(raw, "scores")
                if not data:
                    log.warning("judge.parse.retry", attempt=attempt, error="No JSON object containing 'scores' found", raw_response=raw)
                    continue
                scores = [FieldScore.model_validate(s) for s in data["scores"]]
                return TriageEvaluation(
                    input_id=inp.id,
                    scores=scores,
                    overall_score=compute_overall(scores),
                    critical_errors=data.get("critical_errors", []),
                    judge_confidence=Confianca(data.get("judge_confidence", "medio")),
                )
            except (json.JSONDecodeError, KeyError, ValueError, Exception) as e:
                log.warning("judge.parse.retry", attempt=attempt, error=str(e), raw_response=raw)
                continue
        raise ValueError("judge failed to produce valid JSON after retries")
