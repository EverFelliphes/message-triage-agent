import { useState } from "react";
import { ChevronRight, X } from "lucide-react";
import { useHistory, useHistoryDetail } from "../api/hooks";
import type { HistoryClassification } from "../api/types";
import { CONFIANCA_BADGE, TIPO_BADGE, TIPO_LABEL } from "../lib/labels";

function StatusBadge({ evaluated }: { evaluated: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        evaluated ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-600"
      }`}
    >
      {evaluated ? "Avaliado" : "Pendente"}
    </span>
  );
}

function ClassificationCard({ item }: { item: HistoryClassification }) {
  const { evaluation } = item;
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-400">#{String(item.id)}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TIPO_BADGE[item.tipo_solicitacao]}`}>
          {TIPO_LABEL[item.tipo_solicitacao]}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${CONFIANCA_BADGE[item.confianca]}`}>
          confiança: {item.confianca}
        </span>
        {evaluation && (
          <span className="ml-auto rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
            score {evaluation.overall_score.toFixed(2)} / 10
          </span>
        )}
      </div>

      <p className="mb-2 text-sm text-slate-700">{item.mensagem}</p>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500 sm:grid-cols-3">
        <span>Área: {item.area_sugerida}</span>
        <span>Ação: {item.proxima_acao}</span>
        <span>Urgência: {item.urgencia}</span>
        {item.empresa && <span>Empresa: {item.empresa}</span>}
        {item.cnpj && <span>CNPJ: {item.cnpj}</span>}
        <span>Latência: {item.latency_ms}ms</span>
      </div>

      {evaluation && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            {evaluation.scores.map((s) => (
              <span key={s.field}>
                {s.field}: <span className="font-medium text-slate-700">{s.score}</span>
              </span>
            ))}
          </div>
          {evaluation.critical_errors.length > 0 && (
            <p className="mt-2 text-xs text-rose-600">
              Erros críticos: {evaluation.critical_errors.join("; ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RunDetailPanel({ runId, onClose }: { runId: string; onClose: () => void }) {
  const detail = useHistoryDetail(runId);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">
          Detalhe do run <span className="font-mono text-xs text-slate-400">{runId.slice(0, 12)}</span>
        </h3>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          aria-label="Fechar detalhe"
        >
          <X size={16} />
        </button>
      </div>

      {detail.isLoading && <div className="text-sm text-slate-400">Carregando run…</div>}
      {detail.isError && (
        <div className="text-sm text-rose-600">
          Falha ao carregar: {(detail.error as Error).message}
        </div>
      )}

      {detail.data && (
        <div className="space-y-3">
          {!detail.data.evaluated && (
            <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-3 text-xs text-slate-500">
              Este run ainda não foi avaliado. Use “Rodar avaliação” no dashboard.
            </p>
          )}
          {detail.data.classifications.map((c, i) => (
            <ClassificationCard key={`${String(c.id)}-${i}`} item={c} />
          ))}
        </div>
      )}
    </section>
  );
}

export default function HistoryPage() {
  const history = useHistory();
  const [selected, setSelected] = useState<string | null>(null);

  const items = history.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">Histórico de classificações</h1>
        <p className="text-sm text-slate-500">
          Todos os runs registrados. Clique em um run para ver as classificações e suas
          avaliações.
        </p>
      </div>

      {history.isLoading && <div className="text-sm text-slate-400">Carregando histórico…</div>}
      {history.isError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Não foi possível carregar o histórico: {(history.error as Error).message}
        </div>
      )}

      {!history.isLoading && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          Nenhum run ainda. Classifique mensagens para popular o histórico.
        </div>
      )}

      {items.length > 0 && (
        <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr className="border-b border-slate-100">
                <th className="px-4 py-3">Data</th>
                <th>Modelo</th>
                <th>Prompt</th>
                <th className="text-right">Itens</th>
                <th className="text-right">Score</th>
                <th className="px-4 text-center">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => {
                const isSelected = selected === r.run_id;
                return (
                  <tr
                    key={r.run_id}
                    onClick={() => setSelected(isSelected ? null : r.run_id)}
                    className={`cursor-pointer border-t border-slate-100 transition hover:bg-slate-50 ${
                      isSelected ? "bg-brand-50" : ""
                    }`}
                  >
                    <td className="px-4 py-2 text-slate-600">
                      {r.timestamp ? new Date(r.timestamp).toLocaleString("pt-BR") : "—"}
                    </td>
                    <td className="text-slate-600">{r.model ?? "—"}</td>
                    <td className="text-slate-600">{r.prompt_version ?? "—"}</td>
                    <td className="text-right text-slate-600">{r.total_classifications}</td>
                    <td className="text-right text-slate-600">
                      {r.mean_score != null ? r.mean_score.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 text-center">
                      <StatusBadge evaluated={r.evaluated} />
                    </td>
                    <td className="pr-3 text-slate-400">
                      <ChevronRight
                        size={16}
                        className={`transition ${isSelected ? "rotate-90" : ""}`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      {selected && <RunDetailPanel runId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
