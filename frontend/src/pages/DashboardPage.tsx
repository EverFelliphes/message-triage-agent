import { useMetrics, useRuns, useTimeline } from "../api/hooks";
import MetricCard from "../components/MetricCard";
import ScoreTimeline from "../components/ScoreTimeline";
import CategoryBreakdown from "../components/CategoryBreakdown";
import CalibrationHeatmap from "../components/CalibrationHeatmap";
import RunReportsControl from "../components/RunReportsControl";
import { humanTipo } from "../lib/labels";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </section>
  );
}

export default function DashboardPage() {
  const metrics = useMetrics();
  const runs = useRuns();
  const timeline = useTimeline();

  if (metrics.isLoading) {
    return <div className="text-sm text-slate-400">Carregando métricas…</div>;
  }
  if (metrics.isError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Não foi possível carregar as métricas: {(metrics.error as Error).message}
      </div>
    );
  }

  const m = metrics.data!;
  const empty = m.total_classifications === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">Dashboard histórico</h1>
        <p className="text-sm text-slate-500">
          Métricas sobre o corpus de runs e avaliações. Atualiza a cada 30s.
        </p>
      </div>

      <RunReportsControl />

      {empty && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          Nenhum run ainda. Classifique mensagens e rode a pipeline de avaliação
          (<code>make examples &amp;&amp; make evaluate</code>) para popular o dashboard.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Runs" value={m.total_runs} />
        <MetricCard label="Classificações" value={m.total_classifications} />
        <MetricCard
          label="Score médio"
          value={m.mean_overall_score ? m.mean_overall_score.toFixed(2) : "—"}
          hint="/ 10 (juiz LLM)"
        />
        <MetricCard label="Latência média" value={`${m.mean_latency_ms.toFixed(0)}ms`} />
      </div>

      <Panel title="Evolução do score">
        <ScoreTimeline data={timeline.data ?? []} />
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Distribuição por categoria">
          <CategoryBreakdown metrics={m} />
        </Panel>
        <Panel title="Matriz de calibração">
          <CalibrationHeatmap metrics={m} />
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <MetricCard label="p50 latência" value={`${m.p50_latency_ms.toFixed(0)}ms`} />
        <MetricCard label="p95 latência" value={`${m.p95_latency_ms.toFixed(0)}ms`} />
        <MetricCard
          label="Fallback / retry"
          value={`${(m.fallback_rate * 100).toFixed(0)}% / ${(m.retry_rate * 100).toFixed(0)}%`}
        />
      </div>

      <Panel title="Runs recentes">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="py-2">Data</th>
                <th>Modelo</th>
                <th>Prompt</th>
                <th className="text-right">Itens</th>
                <th className="text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {(runs.data?.items ?? []).slice(0, 10).map((r) => (
                <tr key={r.run_id} className="border-t border-slate-100">
                  <td className="py-2 text-slate-600">
                    {r.timestamp ? new Date(r.timestamp).toLocaleString("pt-BR") : "—"}
                  </td>
                  <td className="text-slate-600">{r.model ?? "—"}</td>
                  <td className="text-slate-600">{r.prompt_version ?? "—"}</td>
                  <td className="text-right text-slate-600">{r.total_classifications}</td>
                  <td className="text-right text-slate-600">
                    {r.mean_score != null ? r.mean_score.toFixed(2) : "—"}
                  </td>
                </tr>
              ))}
              {(runs.data?.items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-slate-400">
                    Nenhum run ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      {Object.keys(m.critical_error_count_per_category).length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <span className="font-medium">Atenção:</span> erros críticos concentrados em{" "}
          {Object.entries(m.critical_error_count_per_category)
            .map(([tipo, n]) => `${humanTipo(tipo)} (${n})`)
            .join(", ")}
          .
        </div>
      )}
    </div>
  );
}
