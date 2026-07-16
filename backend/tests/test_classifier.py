import json

from conftest import FakeProvider

from triage.classifier import TriageClassifier
from triage.config import get_settings
from triage.schemas import Confianca, ProximaAcao, TriageInput


def _classify(responses, inp):
    settings = get_settings()
    clf = TriageClassifier(settings, provider=FakeProvider(responses))
    return clf.classify(inp)


def test_success(sample_input, sample_output_json):
    out = _classify(sample_output_json, sample_input)
    assert out.tipo_solicitacao.value == "interesse_em_credito_pj"
    assert out.metadata["retry_count"] == 0
    assert out.metadata["fallback"] is False
    assert out.metadata["provider"] == "fake"


def test_retry_on_malformed_then_valid(sample_input, sample_output_json):
    out = _classify(["isso não é json", sample_output_json], sample_input)
    assert out.metadata["retry_count"] == 1
    assert out.metadata["fallback"] is False


def test_fallback_after_max_retries(sample_input):
    out = _classify("nunca é json", sample_input)
    assert out.metadata["fallback"] is True
    assert out.confianca is Confianca.BAIXO
    assert out.proxima_acao is ProximaAcao.ENVIAR_PARA_ANALISE_MANUAL


def test_extractor_cnpj_overrides_llm():
    payload = json.loads(_valid_payload())
    payload["cnpj"] = None  # model missed it
    inp = TriageInput(id=9, mensagem="Segue contrato da empresa 45.723.174/0001-10.")
    out = _classify(json.dumps(payload), inp)
    assert out.cnpj == "45.723.174/0001-10"


def test_low_confidence_forces_manual_review():
    payload = json.loads(_valid_payload())
    payload["confianca"] = "baixo"
    payload["proxima_acao"] = "encaminhar_comercial"
    inp = TriageInput(id=1, mensagem="Mensagem ambígua qualquer.")
    out = _classify(json.dumps(payload), inp)
    assert out.proxima_acao is ProximaAcao.ENVIAR_PARA_ANALISE_MANUAL


def test_high_urgency_extractor_overrides_low():
    payload = json.loads(_valid_payload())
    payload["urgencia"] = "baixa"
    inp = TriageInput(id=1, mensagem="Preciso disso HOJE, é urgente!")
    out = _classify(json.dumps(payload), inp)
    assert out.urgencia.value == "alta"


def _valid_payload() -> str:
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
            "justificativa": "Justificativa longa o suficiente para validar corretamente aqui.",
        }
    )


def test_classifier_extract_json_with_other_braces(sample_input):
    payload = _valid_payload()
    raw_response = (
        "Pensamento: {analisar_urgencia} -> {alta}.\n"
        "Configurações: {'debug': false}.\n"
        f"JSON final:\n{payload}"
    )
    out = _classify(raw_response, sample_input)
    assert out.tipo_solicitacao.value == "interesse_em_credito_pj"
    assert out.metadata["fallback"] is False
    assert out.metadata["retry_count"] == 0


def test_transient_error_retry():
    from triage.providers import retry_on_transient_error
    
    calls = 0
    
    class TransientError(Exception):
        pass
        
    @retry_on_transient_error(max_attempts=3, initial_delay=0.01, backoff_factor=1.0)
    def dummy_api_call():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("503 Service Unavailable")
        return "success"
        
    res = dummy_api_call()
    assert res == "success"
    assert calls == 3


def test_non_transient_error_does_not_retry():
    from triage.providers import retry_on_transient_error
    
    calls = 0
    
    class FatalError(Exception):
        pass
        
    @retry_on_transient_error(max_attempts=3, initial_delay=0.01, backoff_factor=1.0)
    def dummy_api_call():
        nonlocal calls
        calls += 1
        raise FatalError("Invalid API key")
        
    import pytest
    with pytest.raises(FatalError):
        dummy_api_call()
        
    assert calls == 1
