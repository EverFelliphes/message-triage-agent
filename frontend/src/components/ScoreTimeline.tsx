import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimelinePoint } from "../api/types";

export default function ScoreTimeline({ data }: { data: TimelinePoint[] }) {
  const chartData = data.map((p) => ({
    time: new Date(p.timestamp).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit" }),
    score: p.score,
  }));

  if (chartData.length === 0) {
    return <EmptyChart label="Sem avaliações ainda — rode a pipeline de avaliação." />;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
        <YAxis domain={[0, 10]} tick={{ fontSize: 12 }} stroke="#94a3b8" />
        <Tooltip />
        <Line type="monotone" dataKey="score" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function EmptyChart({ label }: { label: string }) {
  return (
    <div className="grid h-[260px] place-items-center rounded-md border border-dashed border-slate-200 text-sm text-slate-400">
      {label}
    </div>
  );
}
