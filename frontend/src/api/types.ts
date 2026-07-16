// TypeScript mirrors of the backend Pydantic contracts (BE-03, BE-08, BE-11).

export type TipoSolicitacao =
  | "interesse_em_credito_pj"
  | "atualizacao_cadastral"
  | "envio_de_documentacao"
  | "solicitacao_de_segunda_via"
  | "duvida_sobre_operacao_financeira"
  | "pendencia_de_informacao"
  | "fora_do_escopo";

export type AreaSugerida =
  | "comercial"
  | "operacoes"
  | "cadastro"
  | "atendimento"
  | "analise_manual"
  | "nao_aplicavel";

export type ProximaAcao =
  | "encaminhar_comercial"
  | "encaminhar_operacoes"
  | "solicitar_informacoes_complementares"
  | "registrar_pendencia"
  | "enviar_para_analise_manual"
  | "marcar_como_fora_do_escopo";

export type Confianca = "alto" | "medio" | "baixo";
export type Urgencia = "alta" | "media" | "baixa";

export interface TriageInput {
  id: number | string;
  assunto?: string | null;
  mensagem: string;
}

export interface TriageOutput {
  id: number | string;
  tipo_solicitacao: TipoSolicitacao;
  empresa: string | null;
  cnpj: string | null;
  documentos_identificados: string[];
  data_mencionada: string | null;
  area_sugerida: AreaSugerida;
  proxima_acao: ProximaAcao;
  confianca: Confianca;
  urgencia: Urgencia;
  justificativa: string;
  metadata: Record<string, unknown>;
}

export interface RunSummary {
  run_id: string;
  timestamp: string | null;
  model: string | null;
  prompt_version: string | null;
  total_classifications: number;
  mean_score: number | null;
}

export interface RunsPage {
  total: number;
  items: RunSummary[];
}

export interface TimelinePoint {
  timestamp: string;
  score: number;
}

// --- history (GET /history, GET /history/{id}) -----------------------------
// Storage-agnostic contract: the frontend knows nothing about how runs are
// persisted — only these DTOs returned by the history endpoints.

export interface HistoryItem {
  run_id: string;
  timestamp: string | null;
  model: string | null;
  prompt_version: string | null;
  total_classifications: number;
  mean_score: number | null;
  evaluated: boolean;
}

export interface HistoryPage {
  total: number;
  items: HistoryItem[];
}

export interface HistoryFieldScore {
  field: string;
  score: number;
  reasoning: string;
}

export interface HistoryEvaluation {
  overall_score: number;
  scores: HistoryFieldScore[];
  critical_errors: string[];
  judge_confidence: Confianca;
}

export interface HistoryClassification {
  id: number | string;
  assunto: string | null;
  mensagem: string;
  tipo_solicitacao: TipoSolicitacao;
  area_sugerida: AreaSugerida;
  proxima_acao: ProximaAcao;
  confianca: Confianca;
  urgencia: Urgencia;
  empresa: string | null;
  cnpj: string | null;
  documentos_identificados: string[];
  data_mencionada: string | null;
  justificativa: string;
  latency_ms: number;
  evaluation: HistoryEvaluation | null;
}

export interface HistoryDetail {
  run_id: string;
  timestamp: string | null;
  model: string | null;
  prompt_version: string | null;
  evaluated: boolean;
  classifications: HistoryClassification[];
}

// --- reports (POST /reports/run, GET /reports/pending) ---------------------

export interface PendingReports {
  pending: number;
  run_ids: string[];
}

export interface EvaluatedRun {
  run_id: string;
  total_items: number;
  score: number;
  delta: number;
  baseline_score: number;
  regressed: boolean;
}

export interface RunReportsResponse {
  status: "running";
  message: string;
}

export interface ReportsStatusResponse {
  status: "idle" | "running" | "completed" | "failed";
  progress: number;
  total: number;
  error: string | null;
  result: {
    requested_limit: number | null;
    total_evaluated: number;
    evaluated: EvaluatedRun[];
    mean_overall_score: number;
    total_evaluations: number;
  } | null;
}

export interface AggregateMetrics {
  total_runs: number;
  total_classifications: number;
  total_evaluations: number;
  time_range: [string, string] | null;
  mean_overall_score: number;
  score_trend: [string, number][];
  score_per_field_over_time: Record<string, [string, number][]>;
  mean_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  fallback_rate: number;
  retry_rate: number;
  confidence_calibration_matrix: Record<string, Record<string, number>>;
  calibration_score: number;
  category_distribution: Record<string, number>;
  per_category_mean_score: Record<string, number>;
  critical_error_count_per_category: Record<string, number>;
  prompt_version_performance: Record<string, number>;
  model_performance: Record<string, number>;
}
