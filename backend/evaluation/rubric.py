"""Evaluation rubric (BE-09).

Weighted, per-field Likert (1-``MAX_SCORE``) rubric used by the LLM judge. Weights
sum to 1.0 and ``compute_overall`` returns their weighted mean on the same scale.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from triage.schemas import Confianca

# Top of the Likert scale. Anchors below are described at 1 / 5 / MAX_SCORE; the
# judge may use any integer in between.
MAX_SCORE = 10

# Per-field weights (must sum to 1.0). ``entidades`` bundles empresa+cnpj+documentos.
RUBRIC: dict[str, dict] = {
    "tipo_solicitacao": {
        "weight": 0.30,
        "criterion": "A categoria escolhida corresponde à intenção real da mensagem?",
        "scale": {
            1: "Categoria claramente errada.",
            5: "Categoria plausível mas discutível / ambiguidade mal resolvida.",
            10: "Categoria correta e inequívoca.",
        },
    },
    "entidades": {
        "weight": 0.25,
        "criterion": "Empresa, CNPJ e documentos foram extraídos corretamente e sem invenção?",
        "scale": {
            1: "Entidades erradas ou alucinadas.",
            5: "Parcialmente corretas / alguma omissão.",
            10: "Todas as entidades presentes extraídas corretamente.",
        },
    },
    "proxima_acao": {
        "weight": 0.20,
        "criterion": "A próxima ação é a rota operacional correta para o tipo?",
        "scale": {
            1: "Ação incoerente com o tipo.",
            5: "Ação aceitável mas subótima.",
            10: "Ação correta segundo a matriz de decisão.",
        },
    },
    "confianca": {
        "weight": 0.15,
        "criterion": "A confiança auto-reportada está calibrada com a real dificuldade?",
        "scale": {
            1: "Descalibrada (alta confiança em erro, ou baixa em acerto óbvio).",
            5: "Parcialmente calibrada.",
            10: "Bem calibrada.",
        },
    },
    "justificativa": {
        "weight": 0.10,
        "criterion": "A justificativa cita o trecho relevante e sustenta a decisão?",
        "scale": {
            1: "Genérica ou não sustenta a decisão.",
            5: "Sustenta parcialmente.",
            10: "Cita o trecho e sustenta bem a decisão.",
        },
    },
}

assert abs(sum(f["weight"] for f in RUBRIC.values()) - 1.0) < 1e-9, "rubric weights must sum to 1.0"


class FieldScore(BaseModel):
    field: str
    score: int = Field(ge=1, le=MAX_SCORE)
    reasoning: str


class TriageEvaluation(BaseModel):
    input_id: int | str
    scores: list[FieldScore]
    overall_score: float
    critical_errors: list[str] = Field(default_factory=list)
    judge_confidence: Confianca


def compute_overall(scores: list[FieldScore]) -> float:
    """Weighted mean of field scores (fields absent from RUBRIC are ignored)."""
    total_weight = 0.0
    acc = 0.0
    for s in scores:
        field = RUBRIC.get(s.field)
        if field is None:
            continue
        acc += s.score * field["weight"]
        total_weight += field["weight"]
    if total_weight == 0:
        return 0.0
    return round(acc / total_weight, 4)
