"""Prompt engineering (BE-05).

Applies empirical findings from the literature:
- Persona prompting (Vatsal & Dubey 2024).
- Few-shot with hand-picked, ambiguity-covering examples (Khrapunova 2025).
- Static least-to-most ordering — most representative example last, nearest the
  query, to exploit recency bias (Khrapunova 2025; Zhao et al. 2021).
- NO Chain-of-Thought / ``Reasoning:`` traces in the examples: CoT did not help
  classification empirically (Khrapunova 2025). Reasoning is reserved for the judge.
- Classify-then-justify ordering + Format-Restricting Instructions instead of full
  constrained decoding (Tam et al. 2024).
"""

from __future__ import annotations

import json

from .schemas import TriageInput

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
Você é um analista de triagem em uma instituição financeira brasileira, \
especializado em identificar solicitações de clientes PJ.

Sua tarefa: classificar a mensagem recebida e devolver um JSON estruturado.

Taxonomia de tipo_solicitacao (escolha exatamente um):
- interesse_em_credito_pj: cliente demonstra interesse em crédito, empréstimo ou financiamento PJ.
- atualizacao_cadastral: pedido de alteração de dados cadastrais (endereço, sócios, contato).
- envio_de_documentacao: cliente ANEXA ou informa que está enviando documentos solicitados.
- solicitacao_de_segunda_via: pedido de segunda via de boleto, contrato, comprovante etc.
- duvida_sobre_operacao_financeira: pergunta sobre uma operação, taxa, saldo ou funcionamento.
- pendencia_de_informacao: falta informação/documento do cliente para prosseguir (pendência aberta).
- fora_do_escopo: mensagem sem relação com atendimento PJ da instituição.

Matriz de decisão (proxima_acao padrão por tipo):
- interesse_em_credito_pj  -> encaminhar_comercial (area comercial)
- atualizacao_cadastral    -> encaminhar_operacoes (area cadastro)
- envio_de_documentacao    -> encaminhar_operacoes (area operacoes)
- solicitacao_de_segunda_via -> encaminhar_operacoes (area atendimento)
- duvida_sobre_operacao_financeira -> solicitar_informacoes_complementares (area atendimento)
- pendencia_de_informacao  -> registrar_pendencia (area operacoes)
- fora_do_escopo           -> marcar_como_fora_do_escopo (area nao_aplicavel)

Regras de saída:
1. Classifique primeiro.
2. Justifique depois, citando o trecho da mensagem que fundamenta a decisão.
3. Use "confianca": "baixo" quando a mensagem for ambígua ou faltar contexto.
4. Extraia empresa, cnpj, documentos_identificados e data_mencionada quando presentes.

Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois, no formato:
{
  "id": <id>,
  "tipo_solicitacao": <enum>,
  "empresa": <string|null>,
  "cnpj": <string|null>,
  "documentos_identificados": [<string>],
  "data_mencionada": <"YYYY-MM-DD"|null>,
  "area_sugerida": <enum>,
  "proxima_acao": <enum>,
  "confianca": "alto"|"medio"|"baixo",
  "urgencia": "alta"|"media"|"baixa",
  "justificativa": <string de 20 a 280 caracteres>
}
"""


def _format_input(inp: TriageInput) -> str:
    assunto = inp.assunto or "(sem assunto)"
    return f"id: {inp.id}\nassunto: {assunto}\nmensagem: {inp.mensagem}"


# Hand-picked few-shot examples, ordered least-to-most representative.
# Each is (input, expected_output_dict). No reasoning traces (CoT rejected).
FEW_SHOT_EXAMPLES: list[dict] = [
    # 1) Ambiguity: sending docs vs. pending information.
    {
        "input": TriageInput(
            id="ex1",
            assunto="Documentos",
            mensagem="Conforme solicitado, segue em anexo o contrato social atualizado.",
        ),
        "output": {
            "id": "ex1",
            "tipo_solicitacao": "envio_de_documentacao",
            "empresa": None,
            "cnpj": None,
            "documentos_identificados": ["contrato social"],
            "data_mencionada": None,
            "area_sugerida": "operacoes",
            "proxima_acao": "encaminhar_operacoes",
            "confianca": "alto",
            "urgencia": "baixa",
            "justificativa": "Cliente anexa documento solicitado ('segue em anexo o contrato social').",
        },
    },
    # 2) Ambiguity: cadastral update vs. credit interest.
    {
        "input": TriageInput(
            id="ex2",
            assunto="Atualização",
            mensagem="Mudamos de endereço e queremos atualizar o cadastro da empresa.",
        ),
        "output": {
            "id": "ex2",
            "tipo_solicitacao": "atualizacao_cadastral",
            "empresa": None,
            "cnpj": None,
            "documentos_identificados": [],
            "data_mencionada": None,
            "area_sugerida": "cadastro",
            "proxima_acao": "encaminhar_operacoes",
            "confianca": "alto",
            "urgencia": "baixa",
            "justificativa": "Pedido explícito de atualizar cadastro por mudança de endereço da empresa.",
        },
    },
    # 3) Clear out-of-scope.
    {
        "input": TriageInput(
            id="ex3",
            assunto="Oi",
            mensagem="Vocês vendem seguro de carro para pessoa física?",
        ),
        "output": {
            "id": "ex3",
            "tipo_solicitacao": "fora_do_escopo",
            "empresa": None,
            "cnpj": None,
            "documentos_identificados": [],
            "data_mencionada": None,
            "area_sugerida": "nao_aplicavel",
            "proxima_acao": "marcar_como_fora_do_escopo",
            "confianca": "alto",
            "urgencia": "baixa",
            "justificativa": "Mensagem sobre seguro de carro para PF, sem relação com atendimento PJ.",
        },
    },
    # 4) Poorly-formatted CNPJ (tolerance) + credit interest — representative.
    {
        "input": TriageInput(
            id="ex4",
            assunto="Crédito",
            mensagem="A Padaria Aurora (cnpj 11222333/0001-81) tem interesse em uma linha de crédito.",
        ),
        "output": {
            "id": "ex4",
            "tipo_solicitacao": "interesse_em_credito_pj",
            "empresa": "Padaria Aurora",
            "cnpj": "11.222.333/0001-81",
            "documentos_identificados": [],
            "data_mencionada": None,
            "area_sugerida": "comercial",
            "proxima_acao": "encaminhar_comercial",
            "confianca": "alto",
            "urgencia": "baixa",
            "justificativa": "Empresa demonstra interesse em linha de crédito PJ ('interesse em uma linha de crédito').",
        },
    },
]


def _example_messages() -> list[dict]:
    messages: list[dict] = []
    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": _format_input(ex["input"])})
        messages.append(
            {"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)}
        )
    return messages


def build_prompt(inp: TriageInput) -> list[dict]:
    """Return the message list (few-shot pairs + the target input).

    The system prompt is passed separately by the provider, per the SDK contract.
    """
    return [*_example_messages(), {"role": "user", "content": _format_input(inp)}]


def build_correction_prompt(original: str, failed_response: str, error: str) -> list[dict]:
    """Build a self-healing retry turn after a JSON/validation failure."""
    return [
        {"role": "user", "content": original},
        {"role": "assistant", "content": failed_response},
        {
            "role": "user",
            "content": (
                "Sua resposta anterior não pôde ser validada. "
                f"Erro: {error}. "
                "Responda novamente com APENAS um objeto JSON válido no formato pedido, "
                "sem texto adicional."
            ),
        },
    ]
