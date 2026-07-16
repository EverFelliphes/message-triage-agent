import { AlertCircle } from "lucide-react";
import ClassificationForm from "../components/ClassificationForm";
import ClassificationResult from "../components/ClassificationResult";
import { useTriage } from "../api/hooks";

export default function ClassifyPage() {
  const triage = useTriage();

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <h1 className="mb-1 text-lg font-semibold text-slate-800">Classificar mensagem</h1>
        <p className="mb-4 text-sm text-slate-500">
          Envie uma mensagem de cliente PJ e receba a triagem estruturada e auditável.
        </p>
        <ClassificationForm onSubmit={(input) => triage.mutate(input)} loading={triage.isPending} />
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Resultado</h2>
        {triage.isPending && (
          <div className="animate-pulse rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-4 h-6 w-40 rounded bg-slate-200" />
            <div className="mb-2 h-20 rounded bg-slate-100" />
            <div className="h-16 rounded bg-slate-100" />
          </div>
        )}
        {triage.isError && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <AlertCircle size={18} />
            <div>
              <p className="font-medium">Falha ao classificar</p>
              <p className="text-rose-600">{(triage.error as Error).message}</p>
              <button className="mt-2 underline" onClick={() => triage.reset()}>
                Tentar novamente
              </button>
            </div>
          </div>
        )}
        {triage.data && !triage.isPending && <ClassificationResult output={triage.data} />}
        {!triage.data && !triage.isPending && !triage.isError && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white/50 p-8 text-center text-sm text-slate-400">
            O resultado aparecerá aqui.
          </div>
        )}
      </div>
    </div>
  );
}
