"""Classifier orchestration (BE-06).

Runs deterministic extractors, calls the LLM provider with a retry/self-heal loop,
merges deterministic overrides on regulated fields, applies the low-confidence
reinforcement rule, and always returns a valid ``TriageOutput`` (fail-safe).
"""

from __future__ import annotations

import json
import re
import time
import uuid

import structlog
from pydantic import ValidationError

from .config import Settings
from .extractors import detect_urgency, extract_cnpj, extract_dates
from .prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_correction_prompt,
    build_prompt,
)
from .providers import LLMProvider, get_provider
from .schemas import (
    AreaSugerida,
    Confianca,
    ProximaAcao,
    TipoSolicitacao,
    TriageInput,
    TriageOutput,
    Urgencia,
)

log = structlog.get_logger()

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Parse a JSON object from model text, tolerating surrounding prose."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
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
                        # Prioritize objects containing common keys for TriageOutput
                        if "tipo_solicitacao" in data or "justificativa" in data:
                            return data
                        candidates.append(data)
                except json.JSONDecodeError:
                    continue

    if candidates:
        return candidates[0]

    raise json.JSONDecodeError("Could not extract a valid JSON object from model response", text, 0)


class TriageClassifier:
    """Single-call structured classifier with deterministic safeguards."""

    def __init__(self, settings: Settings, provider: LLMProvider | None = None) -> None:
        self.settings = settings
        # Injected provider (tests) or the configured adapter — never an SDK directly.
        self.provider = provider or get_provider(settings)

    def classify(self, inp: TriageInput) -> TriageOutput:
        trace_id = uuid.uuid4().hex
        started = time.perf_counter()
        # Note: we never log the raw message body (LGPD) — only lengths / trace id.
        log.info(
            "triage.request.received",
            trace_id=trace_id,
            input_id=str(inp.id),
            stage="received",
            msg_len=len(inp.mensagem),
            has_assunto=inp.assunto is not None,
        )

        # 1. Deterministic extractors.
        cnpj = extract_cnpj(inp.mensagem)
        dates = extract_dates(inp.mensagem)
        urgency = detect_urgency(inp.mensagem)
        if cnpj is None and re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", inp.mensagem):
            log.info("triage.extractor.cnpj.invalid", trace_id=trace_id)

        # 2-6. LLM call with retry / self-heal.
        messages = build_prompt(inp)
        output, retry_count = self._call_with_retries(inp, messages, trace_id)

        latency_ms = int((time.perf_counter() - started) * 1000)

        is_fallback = output is None
        if output is None:
            log.warning(
                "triage.classification.fallback",
                trace_id=trace_id,
                input_id=str(inp.id),
                stage="merge",
                outcome="fallback",
                latency_ms=latency_ms,
            )
            output = self._fallback_output(inp, reason="LLM output could not be validated")

        # 7. Deterministic merge on regulated fields.
        if cnpj is not None:
            output.cnpj = cnpj
        if urgency == Urgencia.ALTA and output.urgencia == Urgencia.BAIXA:
            output.urgencia = Urgencia.ALTA
        if output.data_mencionada is None and dates:
            output.data_mencionada = dates[0]

        # 8. Reinforcement rule: low confidence always routes to a human.
        if output.confianca == Confianca.BAIXO:
            output.proxima_acao = ProximaAcao.ENVIAR_PARA_ANALISE_MANUAL

        # 9. Metadata.
        output.metadata = {
            "trace_id": trace_id,
            "provider": self.provider.name,
            "model_name": self.provider.model,
            "latency_ms": latency_ms,
            "retry_count": retry_count,
            "prompt_version": PROMPT_VERSION,
            "fallback": is_fallback,
        }
        log.info(
            "triage.classification.completed",
            trace_id=trace_id,
            input_id=str(inp.id),
            stage="completed",
            outcome="fallback" if is_fallback else "success",
            latency_ms=latency_ms,
            retry_count=retry_count,
            tipo=output.tipo_solicitacao.value,
            confianca=output.confianca.value,
        )
        return output

    def _call_with_retries(
        self, inp: TriageInput, messages: list[dict], trace_id: str
    ) -> tuple[TriageOutput | None, int]:
        """Call the provider, self-healing on JSON/validation errors."""
        convo = list(messages)
        last_error = ""
        raw = ""
        for attempt in range(self.settings.max_retries + 1):
            try:
                log.info("triage.llm.call.start", trace_id=trace_id, attempt=attempt)
                raw = self.provider.complete(
                    SYSTEM_PROMPT,
                    convo,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                )
                data = _extract_json(raw)
                data["id"] = inp.id  # the id is ours, never trust the model's copy
                output = TriageOutput.model_validate(data)
                log.info("triage.llm.call.success", trace_id=trace_id, attempt=attempt)
                return output, attempt
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                log.warning(
                    "triage.llm.call.retry",
                    trace_id=trace_id,
                    attempt=attempt,
                    error_type=type(exc).__name__,
                )
                convo = build_correction_prompt(
                    original=messages[-1]["content"],
                    failed_response=raw,
                    error=last_error,
                )
            except Exception as exc:  # provider/transport error — do not retry blindly
                log.error(
                    "triage.llm.call.failed",
                    trace_id=trace_id,
                    input_id=str(inp.id),
                    stage="llm_call",
                    outcome="error",
                    attempt=attempt,
                    error_type=type(exc).__name__,
                )
                raise
        return None, self.settings.max_retries

    def _fallback_output(self, inp: TriageInput, reason: str) -> TriageOutput:
        """Deterministic safe output: route to a human, never crash."""
        return TriageOutput(
            id=inp.id,
            tipo_solicitacao=TipoSolicitacao.FORA_DO_ESCOPO,
            empresa=None,
            cnpj=None,
            documentos_identificados=[],
            data_mencionada=None,
            area_sugerida=AreaSugerida.ANALISE_MANUAL,
            proxima_acao=ProximaAcao.ENVIAR_PARA_ANALISE_MANUAL,
            confianca=Confianca.BAIXO,
            urgencia=detect_urgency(inp.mensagem),
            justificativa=(
                "Não foi possível classificar automaticamente com segurança; "
                "encaminhado para análise manual por precaução."
            ),
            metadata={"fallback_reason": reason},
        )
