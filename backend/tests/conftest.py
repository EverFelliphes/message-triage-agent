"""Shared test fixtures (BE-15).

No test touches a real API: the classifier is driven through an in-memory
``fake_provider``. Dummy keys are set so ``Settings`` validates, and storage is
redirected to a per-test temp dir.
"""

from __future__ import annotations

import os

# Must be set before any triage import triggers Settings validation.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("CLASSIFIER_PROVIDER", "anthropic")

import json  # noqa: E402

import pytest  # noqa: E402

from triage.schemas import TriageInput, TriageOutput  # noqa: E402


class FakeProvider:
    """In-memory LLMProvider returning scripted completions."""

    name = "fake"
    model = "fake-model"

    def __init__(self, responses: list[str] | str):
        self._responses = [responses] if isinstance(responses, str) else list(responses)
        self._i = 0

    def complete(self, system, messages, *, temperature, max_tokens) -> str:
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Point storage at a fresh temp dir per test and reset the settings cache.

    Also redirects the persistent log sink into the temp dir so tests never write
    to the repo's ``storage/logs``.
    """
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    from triage.config import get_settings
    from triage.logging_setup import configure_logging

    get_settings.cache_clear()
    configure_logging("INFO", log_dir=tmp_path / "logs")
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_input() -> TriageInput:
    return TriageInput(id=1, assunto="Crédito", mensagem="Temos interesse em crédito PJ.")


@pytest.fixture
def sample_output_json() -> str:
    return json.dumps(
        {
            "tipo_solicitacao": "interesse_em_credito_pj",
            "empresa": None,
            "cnpj": None,
            "documentos_identificados": [],
            "data_mencionada": None,
            "area_sugerida": "comercial",
            "proxima_acao": "encaminhar_comercial",
            "confianca": "alto",
            "urgencia": "baixa",
            "justificativa": "Cliente demonstra interesse explícito em crédito PJ na mensagem.",
        }
    )


@pytest.fixture
def sample_output(sample_output_json) -> TriageOutput:
    data = json.loads(sample_output_json)
    data["id"] = 1
    return TriageOutput.model_validate(data)


@pytest.fixture
def fake_provider(sample_output_json) -> FakeProvider:
    return FakeProvider(sample_output_json)
