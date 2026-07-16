import type { AggregateMetrics } from "../api/types";

const ORDER = ["baixo", "medio", "alto"];

// Rows = classifier self-reported confidence; columns = judge score bucket.
// Perfect calibration lands on the diagonal.
export default function CalibrationHeatmap({ metrics }: { metrics: AggregateMetrics }) {
  const matrix = metrics.confidence_calibration_matrix;
  const counts = ORDER.flatMap((r) => ORDER.map((c) => matrix?.[r]?.[c] ?? 0));
  const max = Math.max(1, ...counts);

  if (counts.every((c) => c === 0)) {
    return (
      <div className="grid h-[220px] place-items-center rounded-md border border-dashed border-slate-200 text-sm text-slate-400">
        Sem dados de calibração ainda.
      </div>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-[auto_repeat(3,1fr)] gap-1 text-center text-xs">
        <div />
        {ORDER.map((c) => (
          <div key={c} className="pb-1 font-medium text-slate-500">
            juiz: {c}
          </div>
        ))}
        {ORDER.map((row) => (
          <Row key={row} row={row} matrix={matrix} max={max} />
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400">
        Calibração perfeita = diagonal. Score:{" "}
        <span className="font-medium text-slate-600">
          {(metrics.calibration_score * 100).toFixed(0)}%
        </span>
      </p>
    </div>
  );
}

function Row({
  row,
  matrix,
  max,
}: {
  row: string;
  matrix: AggregateMetrics["confidence_calibration_matrix"];
  max: number;
}) {
  return (
    <>
      <div className="flex items-center pr-2 font-medium text-slate-500">conf: {row}</div>
      {ORDER.map((col) => {
        const value = matrix?.[row]?.[col] ?? 0;
        const alpha = value / max;
        return (
          <div
            key={col}
            className="grid aspect-[2/1] place-items-center rounded text-sm font-medium"
            style={{
              backgroundColor: `rgba(37, 99, 235, ${0.08 + alpha * 0.8})`,
              color: alpha > 0.5 ? "white" : "#334155",
            }}
          >
            {value}
          </div>
        );
      })}
    </>
  );
}
