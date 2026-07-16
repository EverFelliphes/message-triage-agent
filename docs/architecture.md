# Arquitetura

## Visão Geral (Overview)

O sistema é estruturado como um pipeline em camadas. Uma mensagem passa por extratores determinísticos e uma única chamada de LLM em paralelo, cujos resultados são mesclados (as regras determinísticas prevalecem sobre campos regulados), passam por uma camada de reforço (baixa confiança → revisão manual), são validados contra um contrato JSON rigoroso e persistidos como artefatos versionados em disco. Um pipeline de avaliação offline julga esses artefatos e alimenta o dashboard.

```
Input → [Extratores] ┐
                     ├→ [Mescla] → [Reforço] → [Validação] → [Armazenamento] → [Juiz] → [Agregação] → [Dashboard]
Input → [Classificador] ┘
```

## Princípios de Design

1. **Separação física entre Regras e IA.** A lógica determinística ([`extractors.py`](../backend/src/triage/extractors.py)) vive em um módulo separado da chamada do LLM ([`classifier.py`](../backend/src/triage/classifier.py)). A camada de mesclagem garante que as regras determinísticas *sobreponham* o modelo em campos regulados (CNPJ, urgência).
2. **Uma única chamada, uma única resposta.** Uma única execução do LLM retorna toda a estrutura de decisão. Não há cadeias de chamadas (chains) ou loops de agente no fluxo principal de classificação.
3. **Mecanismos de salvaguarda contra falhas (Fail-safe).** Respostas malformadas passam por um loop de auto-correção via prompt de correção. Caso as tentativas se esgotem, retorna-se um fallback determinístico ("encaminhar para análise manual"). Classificações com baixa confiança também são direcionadas para análise humana.
4. **Armazenamento em sistema de arquivos.** Artefatos JSON versionados, cada um carregando uma `schema_version`, gerenciados por uma interface leve de I/O.
5. **Acesso portátil a modelos (independente de provedor).** O classificador depende de um protocolo `LLMProvider`, nunca de um SDK diretamente.

## Camada por Camada

- **Extratores** — validação determinística de CNPJ com dígito verificador (módulo 11), parsing de datas relativas/brasileiras e detecção de palavras-chave de urgência. Funções puras, sem LLM, cobertas por testes unitários.
- **Prompts** ([`prompts.py`](../backend/src/triage/prompts.py)) — persona, taxonomia completa, matriz de decisão e exemplos few-shot ordenados de menor a maior relevância (recency bias), sem Chain-of-Thought (CoT). Veja mais em [prompt_engineering.md](prompt_engineering.md).
- **Provedores** ([`providers.py`](../backend/src/triage/providers.py)) — Protocolo `LLMProvider` + adaptadores específicos para cada SDK. Inclui o decorador `retry_on_transient_error` com backoff exponencial e jitter para contornar instabilidades temporárias de rede (como erros 503 e 429).
- **Classificador** — orquestra extratores → prompts → chamada ao provedor (com tratamento de erro/auto-correção) → mesclagem → reforço de segurança → metadados. Garante o retorno de um `TriageOutput` válido.
- **Armazenamento** ([`storage.py`](../backend/evaluation/storage.py)) — Entrada e saída para `RunRecord` e `EvaluationRecord` usando arquivos versionados.
- **Avaliação** — rubrica de pontuação, LLM-as-a-Judge cruzado, agregador de métricas, gerador de relatórios e runner de CLI.
- **API** ([`api.py`](../backend/src/triage/api.py)) — endpoints para classificação e endpoints de dados para o dashboard. O processamento pesado de relatórios foi delegado ao FastAPI `BackgroundTasks` (`POST /reports/run`) com consulta via `/reports/status` para evitar timeouts de conexões HTTP.
- **Frontend** — painel React + Vite que lê os dados estruturados agregados pelo backend.

## Portabilidade de Modelos — Abstração de Provedor

**Escolha:** Foi definida uma interface `LLMProvider` leve, implementada por adaptadores para cada SDK, selecionados via configuração `settings.classifier_provider`. A troca de provedores (ex.: Claude → Gemini) é feita apenas alterando a configuração, mantendo o classificador e os prompts intactos. Isso isola dependências externas e simplifica testes usando fakes.

**Modelos recomendados por provedor (definidos via `.env`):**

| Função | Provedor | Recomendado | Alternativas |
|---|---|---|---|
| Classificador | anthropic | `claude-sonnet-5` (melhor custo-benefício) | `claude-opus-4-8` (máxima acurácia) · `claude-haiku-4-5` (mais barato) |
| Classificador | gemini | `gemini-2.5-pro` | `gemini-2.5-flash` · `gemini-2.0-flash` |
| Juiz (Judge) | openai | `gpt-4o` | `gpt-4.1` · `gpt-4-turbo` |
| Juiz (Judge) | gemini | `gemini-2.5-pro` | `gemini-2.5-flash` |

*Nota:* O classificador usa Sonnet 5 por padrão, unindo acurácia e eficiência de custos. O juiz offline deve ser mantido em uma **família de modelos diferente** da do classificador para mitigar o viés de preferência própria (self-preference bias).

**Justificativa de não escolha de outras abordagens:**

*   **Pydantic AI:** Excelente para projetos orientados a Pydantic, mas escrever adaptadores próprios mantém a aplicação livre de dependências extras e simplifica a auditoria do fluxo de dados.
*   **Instructor:** Facilita retornos estruturados e retentativas, mas sobrepõe-se ao nosso fluxo customizado de correção/auto-cura e introduz complexidade ao alternar provedores (via LiteLLM).
*   **LiteLLM:** Recomendado para roteamento dinâmico entre dezenas de provedores, mas desnecessário para o escopo inicial focado em poucos provedores fixos.
*   **LangChain:** Framework robusto de orquestração, porém introduz abstrações complexas desnecessárias para uma aplicação que realiza apenas uma única chamada estruturada ao LLM.

## Tecnologias e Técnicas Não Selecionadas e Justificativas

*   **Bancos de Dados Relacionais/NoSQL:** Desnecessários para o volume inicial de dezenas de registros. Arquivos JSON em disco são de leitura simples, servem como trilha de auditoria e podem ser facilmente versionados e visualizados via `git diff`.
*   **Ajuste Fino (Fine-tuning) de Modelos:** Requer um conjunto volumoso de dados rotulados. Técnicas de Few-Shot In-Context Learning (RA-ICL) trazem resultados comparáveis a custo de engenharia muito menor (Khrapunova 2025).
*   **Decodificação Totalmente Restringida (Grammar/Constrained Decoding):** Evitamos devido ao "imposto de restrição" (Tam et al. 2024), onde limitar rigidamente os tokens na saída degrada a capacidade de raciocínio do modelo. Preferimos instruções claras de formato (FRI) + auto-correção via código.
*   **Chain-of-Thought (CoT) na Classificação:** Não trouxe ganho empírico significativo para a tarefa de triagem direta (Khrapunova 2025), além de aumentar custos e latência. O CoT foi reservado exclusivamente para o Juiz offline (onde a tomada de decisão exige raciocínio detalhado).
*   **Juiz LLM Executado em Tempo de Execução (Runtime Judge):** Adicionaria latência crítica ao cliente final. A avaliação e cálculo da rubrica ocorrem em lote assíncrono offline.

## LGPD / PII

Mensagens de clientes corporativos podem conter dados sensíveis (CNPJ, nomes de empresas, telefones). Para manter a conformidade com a LGPD:
*   Os logs estruturados do sistema nunca emitem o conteúdo bruto da mensagem, apenas IDs, comprimentos de texto e tempo de latência.
*   Os dados brutos persistem somente no sistema de arquivos local (`storage/`), permitindo aplicar controle de acesso rígido e políticas automáticas de expiração de dados a nível de infraestrutura de disco.

## Próximos Passos (Gatilhos Quantitativos)

*   **Pipeline de CI:** Configurar lint/testes/build assim que houver colaboração de outros desenvolvedores ou aumento de tráfego de commits.
*   **Gold Set com Rotulagem Humana:** Criar um conjunto de referência (~20–50 amostras) para reportar acurácia real e calibrar a acurácia do Juiz LLM.
*   **RA-ICL:** Introduzir busca por similaridade de exemplos assim que acumularmos entre 500 e 1000 classificações validadas por humanos.
*   **Encoder Ajustado Localmente:** Considerar fine-tuning se o volume de requisições e a exigência de latência abaixo de 100ms justificarem o custo operacional.
