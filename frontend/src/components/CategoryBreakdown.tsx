import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AggregateMetrics } from "../api/types";
import { humanTipo } from "../lib/labels";
import { EmptyChart } from "./ScoreTimeline";

export default function CategoryBreakdown({ metrics }: { metrics: AggregateMetrics }) {
  const data = Object.entries(metrics.category_distribution).map(([tipo, count]) => ({
    tipo: humanTipo(tipo),
    count,
    score: metrics.per_category_mean_score[tipo] ?? 0,
  }));

  if (data.length === 0) return <EmptyChart label="Sem classificações ainda." />;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 40, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="tipo"
          tick={{ fontSize: 10 }}
          stroke="#94a3b8"
          angle={-25}
          textAnchor="end"
          interval={0}
        />
        <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
        <Tooltip />
        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="quantidade" />
      </BarChart>
    </ResponsiveContainer>
  );
}
