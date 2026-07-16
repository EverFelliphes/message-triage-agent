import type { Confianca, TipoSolicitacao } from "../api/types";

// Human labels + Tailwind badge classes, shared across pages.

export const TIPO_LABEL: Record<TipoSolicitacao, string> = {
  interesse_em_credito_pj: "Interesse em crédito PJ",
  atualizacao_cadastral: "Atualização cadastral",
  envio_de_documentacao: "Envio de documentação",
  solicitacao_de_segunda_via: "Segunda via",
  duvida_sobre_operacao_financeira: "Dúvida sobre operação",
  pendencia_de_informacao: "Pendência de informação",
  fora_do_escopo: "Fora do escopo",
};

export const TIPO_BADGE: Record<TipoSolicitacao, string> = {
  interesse_em_credito_pj: "bg-emerald-100 text-emerald-800",
  atualizacao_cadastral: "bg-sky-100 text-sky-800",
  envio_de_documentacao: "bg-indigo-100 text-indigo-800",
  solicitacao_de_segunda_via: "bg-amber-100 text-amber-800",
  duvida_sobre_operacao_financeira: "bg-violet-100 text-violet-800",
  pendencia_de_informacao: "bg-orange-100 text-orange-800",
  fora_do_escopo: "bg-slate-200 text-slate-700",
};

export const CONFIANCA_BADGE: Record<Confianca, string> = {
  alto: "bg-emerald-100 text-emerald-800",
  medio: "bg-amber-100 text-amber-800",
  baixo: "bg-rose-100 text-rose-800",
};

export function humanTipo(t: string): string {
  return TIPO_LABEL[t as TipoSolicitacao] ?? t;
}
