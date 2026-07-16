import { useState } from "react";
import { AlertTriangle, ChevronDown, FileText, Building2, Clock } from "lucide-react";
import type { TriageOutput } from "../api/types";
import { CONFIANCA_BADGE, humanTipo, TIPO_BADGE } from "../lib/labels";

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm text-slate-700">{value || "—"}</div>
    </div>
  );
}

export default function ClassificationResult({ output }: { output: TriageOutput }) {
  const [showJson, setShowJson] = useState(false);
  const [showMeta, setShowMeta] = useState(false);
  const lowConfidence = output.confianca === "baixo";

  return (
    <div
      className={`rounded-xl border bg-white p-5 shadow-sm ${
        lowConfidence ? "border-rose-300 ring-1 ring-rose-100" : "border-slate-200"
      }`}
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${TIPO_BADGE[output.tipo_solicitacao]}`}
        >
          {humanTipo(output.tipo_solicitacao)}
        </span>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${CONFIANCA_BADGE[output.confianca]}`}
        >
          confiança: {output.confianca}
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          urgência: {output.urgencia}
        </span>
        {lowConfidence && (
          <span className="ml-auto flex items-center gap-1 text-xs font-medium text-rose-600">
            <AlertTriangle size={14} /> análise manual
          </span>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Pill label="Empresa" value={output.empresa ?? ""} />
        <Pill label="CNPJ" value={output.cnpj ?? ""} />
        <Pill label="Data" value={output.data_mencionada ?? ""} />
        <div className="col-span-2 rounded-md bg-slate-50 px-3 py-2 sm:col-span-3">
          <div className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-wide text-slate-400">
            <FileText size={12} /> Documentos
          </div>
          <div className="text-sm text-slate-700">
            {output.documentos_identificados.length
              ? output.documentos_identificados.join(", ")
              : "—"}
          </div>
        </div>
      </div>

      <div className="mb-3 rounded-md bg-brand-50 px-3 py-2">
        <div className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-brand-700">
          <Building2 size={12} /> Próxima ação · {output.area_sugerida}
        </div>
        <div className="text-sm font-medium text-brand-900">{output.proxima_acao}</div>
      </div>

      <blockquote className="border-l-4 border-slate-200 pl-3 text-sm italic text-slate-600">
        {output.justificativa}
      </blockquote>

      <div className="mt-4 space-y-2 text-xs">
        <button
          className="flex items-center gap-1 text-slate-500 hover:text-slate-700"
          onClick={() => setShowMeta((v) => !v)}
        >
          <Clock size={12} /> Metadados <ChevronDown size={12} />
        </button>
        {showMeta && (
          <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-[11px] text-slate-100">
            {JSON.stringify(output.metadata, null, 2)}
          </pre>
        )}
        <button
          className="flex items-center gap-1 text-slate-500 hover:text-slate-700"
          onClick={() => setShowJson((v) => !v)}
        >
          JSON completo <ChevronDown size={12} />
        </button>
        {showJson && (
          <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-[11px] text-slate-100">
            {JSON.stringify(output, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
