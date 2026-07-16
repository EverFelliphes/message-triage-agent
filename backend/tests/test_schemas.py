import pytest
from pydantic import ValidationError

from triage.schemas import TipoSolicitacao, TriageInput, TriageOutput

_BASE = {
    "id": 1,
    "tipo_solicitacao": "interesse_em_credito_pj",
    "area_sugerida": "comercial",
    "proxima_acao": "encaminhar_comercial",
    "confianca": "alto",
    "urgencia": "baixa",
    "justificativa": "Justificativa suficientemente longa para passar na validação.",
}


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        TriageOutput.model_validate({**_BASE, "campo_extra": "x"})


def test_invalid_enum_rejected():
    with pytest.raises(ValidationError):
        TriageOutput.model_validate({**_BASE, "confianca": "altíssimo"})


def test_justificativa_too_short():
    with pytest.raises(ValidationError):
        TriageOutput.model_validate({**_BASE, "justificativa": "curta"})


def test_justificativa_too_long():
    with pytest.raises(ValidationError):
        TriageOutput.model_validate({**_BASE, "justificativa": "x" * 281})


def test_valid_output():
    out = TriageOutput.model_validate(_BASE)
    assert out.tipo_solicitacao is TipoSolicitacao.INTERESSE_EM_CREDITO_PJ
    assert out.documentos_identificados == []


def test_input_requires_message():
    with pytest.raises(ValidationError):
        TriageInput(id=1, mensagem="")


def test_enum_values_match_enunciado():
    assert {t.value for t in TipoSolicitacao} == {
        "interesse_em_credito_pj",
        "atualizacao_cadastral",
        "envio_de_documentacao",
        "solicitacao_de_segunda_via",
        "duvida_sobre_operacao_financeira",
        "pendencia_de_informacao",
        "fora_do_escopo",
    }
