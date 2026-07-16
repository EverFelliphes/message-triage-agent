# Engenharia de Prompt (Prompt Engineering)

O prompt é o elemento de maior alavancagem para a qualidade da classificação do sistema. Cada decisão tomada no seu design é fruto de testes empíricos de performance. O código de implementação está localizado em [`prompts.py`](../backend/src/triage/prompts.py).

---

## Estrutura do Prompt

A estrutura é composta pela instrução do sistema (`system` - englobando persona, taxonomia completa de classificação, matriz de decisão de roteamento e formatação de saída esperada) seguida por exemplos few-shot de perguntas e respostas selecionados manualmente, e finalmente a mensagem a ser triada. A instrução do sistema é enviada separadamente da lista de turnos de conversa, respeitando os contratos de SDK modernos.

Trecho de exemplo:
> Você é um analista de triagem em uma instituição financeira brasileira, especializado em identificar solicitações de clientes PJ. […] 1. Classifique primeiro. 2. Justifique depois, citando o trecho da mensagem. […] Responda SOMENTE com um objeto JSON válido.

---

## Escolhas de Design de Prompts

| Escolha | Motivação | Referência |
|---|---|---|
| **Definição de Persona** | Contextualiza a IA no papel de triagem corporativa, ajustando vocabulário e rigor | Vatsal & Dubey 2024 |
| **4 Exemplos Few-Shot Estáticos** | Cobrem intencionalmente as ambiguidades mais comuns (ex.: envio de documentos vs pendências cadastrais), casos fora do escopo e CNPJs mal formatados | Khrapunova 2025 |
| **Ordenação Reversa (Least-to-Most)** | Organiza os exemplos do menos relevante ao mais representativo por último (próximo à pergunta final), aproveitando o viés de recência do modelo | Zhao et al. 2021; Khrapunova 2025 |
| **Sem CoT na Classificação** | O Chain-of-Thought não trouxe ganhos na classificação direta, mas adicionaria tokens redundantes e aumentaria a latência | Khrapunova 2025 |
| **Classificar Primeiro, Justificar Depois** | Obriga o modelo a tomar a decisão lógica estruturada antes de justificar, evitando racionalizações inventadas (confabulações post-hoc) | Engenharia Interna |
| **Temperatura 0** | Garante determinismo e reprodutibilidade máxima para auditoria técnica | Prática Comum |

---

## Instruções de Formato (FRI) vs. Decodificação Restringida

Adotamos **Instruções de Restrição de Formato (Format-Restricting Instructions - FRI)**, pedindo explicitamente o JSON em um formato específico e aplicando validação rigorosa com Pydantic, em vez de usar decodificação restringida por gramática (constrained decoding) no motor do modelo. 

Pesquisas (Tam et al. 2024) documentam o "imposto de restrição": quanto mais rigidamente você força os tokens de saída sintaticamente no momento de geração (decodificação), maior é a perda de raciocínio da IA. O uso de FRI mantém a inteligência lógica intacta e transfere a validação e garantia de formato para um loop externo de código, muito mais eficiente e barato.

---

## Retentativas e Loop de Auto-Cura (Self-Healing)

Se ocorrer uma falha ao decodificar o JSON ou no schema de validação do Pydantic, o classificador executa uma retentativa enviando ao modelo a resposta anterior inválida e a mensagem de erro específica gerada pelo Python, instruindo-o a se auto-corrigir. 

Se as tentativas (`max_retries`) se esgotarem, o sistema aciona um fallback determinístico (encaminha para análise manual com baixa confiança), garantindo que a aplicação nunca quebre.

Adicionalmente, utilizamos a função utilitária `extract_json_object` que escaneia e valida strings contendo chaves `{}` do maior bloco para o menor, conseguindo capturar com sucesso o objeto JSON desejado mesmo se o modelo incluir conversas ou introduções textuais antes ou depois da estrutura. O limite de resposta padrão está configurado como `max_tokens=4096` para garantir que respostas ricas do Juiz (contendo o raciocínio detalhado de rubricas de avaliação) não sofram cortes ou truncamentos.

---

## Mesclagem Determinística (Merge Layer)

Para assegurar o cumprimento de regras estritas, algoritmos determinísticos rodam antes do modelo e têm prioridade de substituição:
*   Se um CNPJ válido com dígito verificador correto for extraído por expressão regular, ele substitui qualquer CNPJ gerado pelo modelo.
*   Palavras-chave explícitas de alta urgência forçam a urgência do ticket para alta, mesmo se o modelo classificar como baixa.
O LLM nunca tem a palavra final sobre campos que regras determinísticas de negócio conseguem auditar com precisão absoluta.

---

## Versionamento de Prompts

A constante `PROMPT_VERSION` é incluída nos metadados de cada classificação gravada. Isso viabiliza a execução de testes A/B ou testes de sombra (Shadow Testing) em ambientes de homologação. É possível executar uma nova versão de prompt em paralelo com o de produção e submeter ambos ao Juiz offline para medir os scores médios agregados antes de realizar o deploy definitivo.

---

## Referências

Wei et al. 2022; Vatsal & Dubey 2024; Zhao et al. 2021; Tam et al. 2024 — consulte o [`README.md`](../README.md#referencias) na raiz.
