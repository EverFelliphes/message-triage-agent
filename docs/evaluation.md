# Avaliação (Evaluation)

## O que está Implementado vs. Roadmap

*   **Implementado:** Avaliador offline cruzado (LLM-as-a-Judge), rubrica de qualidade com pesos específicos, persistência de avaliações em arquivos estruturados e versionados, agregação agregada de runs históricas (tendência de score, scores por categoria, matriz de calibração, percentis de latência, taxas de fallback/retentativa, detecção de regressão), relatórios analíticos em Markdown e dashboard visual.
*   **Roadmap:** Rota de revisão com participação humana (human-in-the-loop), conjunto de validação padrão-ouro (gold set base), monitoramento de produção com detecção de desvio (drift) e verificações de regressão automatizadas em esteiras de CI.

---

## Metodologia

*   **Avaliador Cruzado entre Famílias (LLM-as-a-Judge):** (Zheng et al. 2023) — Se o Claude classifica, utilizamos o **GPT-4 ou Gemini** para avaliar. Esta é uma escolha de design intencional para mitigar o **viés de preferência própria** (self-preference bias), onde uma família de modelos tende a dar pontuações maiores para si mesma. O avaliador reutiliza a mesma abstração `LLMProvider`. Se a chave do provedor cruzado não estiver configurada, o sistema gera um alerta de aviso informando que a mitigação de viés foi perdida.
*   **Rubrica de Pontuação Ponderada:** ([`rubric.py`](../backend/evaluation/rubric.py)) — Escala Likert de 1 a 10 por campo avaliado, com pesos que somam 1.0: `tipo_solicitacao` (peso 0.30), `entidades` (peso 0.25), `proxima_acao` (peso 0.20), `confianca` (peso 0.15) e `justificativa` (peso 0.10). O Chain-of-Thought (CoT) está habilitado no avaliador para permitir análises e justificativas ricas antes de emitir a nota.
*   **Artefatos Versionados:** Cada classificação de teste (run) e cada avaliação (evaluation) correspondente gera um arquivo JSON portando a assinatura do esquema (`schema_version`), unificáveis por chaves compostas de `run_id` e `input_id`.
*   **Agregação e Detecção de Regressão:** ([`aggregator.py`](../backend/evaluation/aggregator.py)) — Funções puras aplicadas sobre os JSONs em disco. O método `detect_regression` sinaliza se a média de um run recente caiu abaixo de um limite de tolerância configurável em relação à base de referência histórica.
*   **Execução Assíncrona e Polling:** O pipeline do avaliador é executado em segundo plano usando `BackgroundTasks` do FastAPI para suportar a avaliação de múltiplos runs sem causar estouro de tempo limite (timeout) do servidor. O progresso é enviado ao frontend React em tempo real por meio de polling e exibido em formato de barra de progresso.

---

## Limitações Conhecidas do LLM-as-a-Judge

*   **Ausência de Gabarito Real (Ground Truth):** A pontuação emitida é a opinião de um modelo de IA sobre o desempenho de outro, não a acurácia real. Este é o principal motivo pelo qual a criação de um Gold Set rotulado por humanos é prioridade no roadmap.
*   **Viés de Posição / Verbosidade:** Modelos de avaliação podem favorecer respostas mais longas ou que aparecem primeiro no contexto.
*   **Viés de Preferência Própria:** Mitigado através do uso de provedores cruzados, porém não eliminado por completo.
*   **Amostragem Reduzida (Small-N):** Métricas como percentis de latência e detecção de regressão em pequenos lotes são apenas *indicativas*, ganhando relevância estatística real apenas com o aumento contínuo do volume de avaliações.

---

## Análise de Modos de Falha (Failure-Mode Analysis)

Duas visões principais no painel ajudam a identificar falhas sistemáticas sem necessidade de gabarito humano:
*   **Matriz de Calibração:** Cruza a confiança autodeclarada do classificador (linhas) com os intervalos de nota do juiz (colunas). Concentrações fora da diagonal indicam que a auto-avaliação do modelo é pouco confiável, o que é crítico, pois a regra de desvio automático para "análise manual" depende desse indicador.
*   **Taxa de Erros por Categoria:** Os valores de contagem de erros críticos e pontuação média por categoria de taxonomia revelam onde o modelo se confunde (ex.: classes parecidas ou ambíguas), ajudando a identificar quais exemplos few-shot de prompts precisam de refinamento.

---

## Gatilhos do Roadmap

*   **Revisão Humana:** Amostrar periodicamente de 5% a 10% do tráfego produtivo e enviá-lo a uma fila de conferência.
*   **Gold Set e Busca Semântica:** Reunir uma base de 500 a 1000 amostras revisadas por especialistas para habilitar Retrieval-Augmented In-Context Learning (RA-ICL).
*   **Monitoramento em Produção:** Painéis medindo desvios semânticos (data drift) e variações graduais de pontuação.
*   **Esteiras de CI Integradas:** Interromper construções de build automáticas caso o executor offline `detect_regression` acuse quedas de nota sistemáticas em relação à baseline.

---

## Referências

Zheng et al. 2023; Khrapunova 2025 — consulte o [`README.md`](../README.md#referencias) na raiz.
