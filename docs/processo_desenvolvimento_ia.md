# Processo de Desenvolvimento Assistido por IA

Este documento registra como nós (desenvolvedor humano e eu, Antigravity) colaboramos em regime de *pair programming* para conceber, implementar, testar e otimizar este projeto. 

---

## 📋 1. Desenvolvimento Orientado por Especificações (Spec-Driven Development)

Adotamos a metodologia de **Spec-Driven Development (SDD)**. Antes de iniciar qualquer linha de código, o escopo foi delineado em especificações de requisitos.
*   Essas especificações detalhadas atuaram como a nossa "fonte da verdade". Elas definiram de forma explícita as restrições, o formato de saída esperado, e as regras de tratamento de erros.
*   Em vez de programarmos por tentativa e erro, as especificações alimentaram o meu contexto como diretrizes estritas. Isso nos ajudou a projetar os contratos Pydantic e os componentes principais de forma cirúrgica, evitando inclusões desnecessárias de dependências pesadas (*over-engineering*).

---

## 🏛️ 2. Design e Definição Arquitetural Iterativa

Nós desenhamos a arquitetura do agente de forma totalmente iterativa antes de implementá-la:
*   **Modularidade de Provedores:** Planejamos uma camada de abstração separada para que as chamadas a modelos externos passassem pelo protocolo `LLMProvider` (disponível em `backend/src/triage/providers.py`). Isso facilitou criar mocks nos testes unitários e alternar entre modelos (Claude, Gemini e OpenAI) por meio de variáveis de ambiente.
*   **Camada de Fusão (Merge Layer):** Estruturamos o pipeline para que os extratores determinísticos (em `backend/src/triage/extractors.py`) rodassem de forma isolada do modelo, dando preferência às regras determinísticas rígidas (como CNPJ e urgências literais) sobre a IA.
*   **Armazenamento Transparente:** Decidimos iniciar o armazenamento dos logs de forma simples com arquivos JSON versionados, permitindo rastrear o comportamento de cada run no histórico do Git de forma simples e auditável.

---

## 📚 3. Validação por Literatura Científica

Nossas escolhas de engenharia de prompt foram embasadas em estudos empíricos recentes sobre o comportamento de LLMs em tarefas de NLP:
*   **Avaliador Offline (Zheng et al. 2023):** Estruturamos o pipeline de *LLM-as-a-Judge* cruzando famílias de modelos (classificador rodando em Claude e juiz rodando em Gemini) especificamente para reduzir o viés de preferência própria.
*   **Instruções de Formato (FRI - Tam et al. 2024):** Preferimos o uso de instruções de formato seguidas de validação sintática externa (Pydantic + loop de correção) a gramáticas rígidas em tempo de decodificação, minimizando o impacto negativo de restrições na capacidade lógica do modelo.
*   **Few-Shot e Viés de Recência (Zhao et al. 2021; Khrapunova 2025):** Organizamos os exemplos few-shot de maneira estática e em ordem reversa (do caso menos representativo ao mais representativo por último) para aproveitar a recência no contexto.

---

## 🔄 4. Otimização de Gargalos e Auto-Cura

Ao longo do caminho, nos deparamos com problemas comuns do mundo real e trabalhamos juntos para solucioná-los:

*   **Resiliência a Falhas de Rede:** Para contornar indisponibilidades temporárias das APIs (erros 503 e 429), criamos um decorador de re-execução (`retry_on_transient_error`) baseado em *Exponential Backoff* com *Jitter* randômico nos adaptadores de provedores.
*   **Robustez no Parser de JSON:** Quando o modelo gerava chaves extras ou introduzia conversas adjacentes, a validação quebrava. Implementamos o `extract_json_object` que faz a varredura balanceada de blocos `{}` para isolar e validar a substring JSON correspondente.
*   **Processamento Assíncrono com Polling:** O processamento síncrono de avaliações offline causava estouros de tempo limite (*gateway timeout*) no servidor em execuções longas. Alteramos a rota `/reports/run` para usar `BackgroundTasks` no FastAPI e atualizamos o frontend React para fazer *polling* em tempo real, informando o progresso (ex: `"Avaliando run X de Y..."`) por meio de uma barra de progresso visual.
