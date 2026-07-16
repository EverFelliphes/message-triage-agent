"""Pydantic contracts (BE-03) — the foundation of the whole system.

Enum values match the enunciado literals exactly; every enumerable output field is
an Enum (never a free string), and ``TriageOutput`` forbids extra keys so the LLM
cannot smuggle unvalidated data past the contract.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TipoSolicitacao(StrEnum):
    INTERESSE_EM_CREDITO_PJ = "interesse_em_credito_pj"
    ATUALIZACAO_CADASTRAL = "atualizacao_cadastral"
    ENVIO_DE_DOCUMENTACAO = "envio_de_documentacao"
    SOLICITACAO_DE_SEGUNDA_VIA = "solicitacao_de_segunda_via"
    DUVIDA_SOBRE_OPERACAO_FINANCEIRA = "duvida_sobre_operacao_financeira"
    PENDENCIA_DE_INFORMACAO = "pendencia_de_informacao"
    FORA_DO_ESCOPO = "fora_do_escopo"


class AreaSugerida(StrEnum):
    COMERCIAL = "comercial"
    OPERACOES = "operacoes"
    CADASTRO = "cadastro"
    ATENDIMENTO = "atendimento"
    ANALISE_MANUAL = "analise_manual"
    NAO_APLICAVEL = "nao_aplicavel"


class ProximaAcao(StrEnum):
    ENCAMINHAR_COMERCIAL = "encaminhar_comercial"
    ENCAMINHAR_OPERACOES = "encaminhar_operacoes"
    SOLICITAR_INFORMACOES_COMPLEMENTARES = "solicitar_informacoes_complementares"
    REGISTRAR_PENDENCIA = "registrar_pendencia"
    ENVIAR_PARA_ANALISE_MANUAL = "enviar_para_analise_manual"
    MARCAR_COMO_FORA_DO_ESCOPO = "marcar_como_fora_do_escopo"


class Confianca(StrEnum):
    ALTO = "alto"
    MEDIO = "medio"
    BAIXO = "baixo"


class Urgencia(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class TriageInput(BaseModel):
    """A single free-text message to triage."""

    id: int | str
    assunto: str | None = None
    mensagem: str = Field(min_length=1)


class TriageOutput(BaseModel):
    """The structured, auditable triage decision. Strict contract: no extra keys."""

    model_config = ConfigDict(extra="forbid")

    id: int | str
    tipo_solicitacao: TipoSolicitacao
    empresa: str | None = None
    cnpj: str | None = None
    documentos_identificados: list[str] = Field(default_factory=list)
    data_mencionada: date | None = None
    area_sugerida: AreaSugerida
    proxima_acao: ProximaAcao
    confianca: Confianca
    urgencia: Urgencia
    justificativa: str = Field(min_length=20, max_length=280)
    metadata: dict = Field(default_factory=dict)
