import { useState, useEffect } from "react";
import { Loader2, PlayCircle } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePendingReports, useRunReports } from "../api/hooks";
import { getReportsStatus } from "../api/client";

// "Rodar reports": triggers the offline LLM-judge evaluation over pending runs.
// Scope is either every pending run, or the N most recent pending ones.

export default function RunReportsControl() {
  const pending = usePendingReports();
  const run = useRunReports();
  const qc = useQueryClient();

  const [scope, setScope] = useState<"all" | "quantity">("all");
  const [quantity, setQuantity] = useState(5);

  // Poll the status every 1s when status is "running"
  const statusQuery = useQuery({
    queryKey: ["reportsStatus"],
    queryFn: getReportsStatus,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "running" ? 1000 : false;
    },
  });

  const status = statusQuery.data?.status ?? "idle";
  const progress = statusQuery.data?.progress ?? 0;
  const total = statusQuery.data?.total ?? 0;
  const error = statusQuery.data?.error;
  const result = statusQuery.data?.result;

  const pendingCount = pending.data?.pending ?? 0;
  const limit = scope === "all" ? null : Math.max(1, quantity);
  const nothingPending = pendingCount === 0;

  // Invalidate queries when evaluation completes
  useEffect(() => {
    if (status === "completed") {
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["history"] });
      qc.invalidateQueries({ queryKey: ["timeline"] });
      qc.invalidateQueries({ queryKey: ["pendingReports"] });
    }
  }, [status, qc]);

  const handleRun = () => {
    run.mutate(limit, {
      onSuccess: () => {
        statusQuery.refetch();
      },
    });
  };

  const isRunning = status === "running" || run.isPending;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">Rodar avaliação (reports)</h3>
          <p className="mt-1 text-sm text-slate-500">
            Executa o juiz LLM sobre os runs ainda não avaliados e atualiza as métricas.
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {pending.isLoading
              ? "Verificando pendências…"
              : `${pendingCount} run(s) pendente(s) de avaliação.`}
          </p>
        </div>

        <div className="flex flex-col items-end gap-3">
          <div className="flex items-center gap-3 text-sm">
            <label className="flex items-center gap-1.5 text-slate-600">
              <input
                type="radio"
                name="report-scope"
                checked={scope === "all"}
                onChange={() => setScope("all")}
                disabled={isRunning}
              />
              Todos os pendentes
            </label>
            <label className="flex items-center gap-1.5 text-slate-600">
              <input
                type="radio"
                name="report-scope"
                checked={scope === "quantity"}
                onChange={() => setScope("quantity")}
                disabled={isRunning}
              />
              Quantidade
            </label>
            <input
              type="number"
              min={1}
              max={Math.max(1, pendingCount)}
              value={quantity}
              disabled={scope !== "quantity" || isRunning}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-16 rounded-md border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-100 disabled:text-slate-400"
            />
          </div>

          <button
            onClick={handleRun}
            disabled={isRunning || nothingPending}
            className="inline-flex items-center gap-2 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRunning ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <PlayCircle size={16} />
            )}
            {isRunning ? "Avaliando…" : "Rodar avaliação"}
          </button>
        </div>
      </div>

      {/* Progress feedback */}
      {status === "running" && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Processando avaliações...</span>
            <span>{total > 0 ? `${progress} de ${total} runs` : "Iniciando..."}</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div
              className="bg-brand-600 h-full transition-all duration-300"
              style={{ width: total > 0 ? `${(progress / total) * 100}%` : "5%" }}
            />
          </div>
        </div>
      )}

      {/* Error state */}
      {(run.isError || status === "failed") && (
        <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          Falha ao rodar avaliação: {run.error ? (run.error as Error).message : error}
        </div>
      )}

      {/* Completed results state */}
      {status === "completed" && result && (
        <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {result.total_evaluated === 0
            ? "Nenhum run pendente para avaliar."
            : `${result.total_evaluated} run(s) avaliado(s). Score médio geral: ${result.mean_overall_score.toFixed(
                2,
              )} sobre ${result.total_evaluations} avaliação(ões).`}
        </div>
      )}
    </section>
  );
}
