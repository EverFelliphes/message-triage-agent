import { useState } from "react";
import { Send, Sparkles } from "lucide-react";
import type { TriageInput } from "../api/types";

// A few seeded demo messages (mirrors backend/examples/inputs.json).
const SAMPLES: { label: string; assunto: string; mensagem: string }[] = [
  {
    label: "Interesse em crédito",
    assunto: "Crédito",
    mensagem:
      "Bom dia, a Transportadora Rocha Ltda (CNPJ 45.723.174/0001-10) gostaria de saber sobre linhas de capital de giro.",
  },
  {
    label: "Envio de documentação",
    assunto: "Documentos",
    mensagem: "Conforme solicitado, segue em anexo o balanço patrimonial e o cartão CNPJ.",
  },
  {
    label: "Urgente + CNPJ",
    assunto: "Urgente",
    mensagem:
      "URGENTE! Precisamos de resposta ainda hoje sobre o financiamento da Metalúrgica Sol, cnpj 11.444.777/0001-61.",
  },
  {
    label: "Fora do escopo",
    assunto: "Oi",
    mensagem: "Vocês patrocinam eventos esportivos? Queria falar sobre uma parceria.",
  },
];

interface Props {
  onSubmit: (input: TriageInput) => void;
  loading: boolean;
}

export default function ClassificationForm({ onSubmit, loading }: Props) {
  const [assunto, setAssunto] = useState("");
  const [mensagem, setMensagem] = useState("");
  const tooShort = mensagem.trim().length < 3;

  return (
    <form
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (tooShort) return;
        onSubmit({ id: Date.now(), assunto: assunto || null, mensagem });
      }}
    >
      <label className="mb-1 block text-sm font-medium text-slate-600">Assunto (opcional)</label>
      <input
        className="mb-4 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
        value={assunto}
        onChange={(e) => setAssunto(e.target.value)}
        placeholder="Ex.: Crédito"
      />

      <label className="mb-1 block text-sm font-medium text-slate-600">Mensagem</label>
      <textarea
        className="h-40 w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
        value={mensagem}
        onChange={(e) => setMensagem(e.target.value)}
        placeholder="Cole aqui a mensagem do cliente…"
      />

      <div className="mt-3 flex items-center gap-2">
        <Sparkles size={14} className="text-slate-400" />
        <span className="text-xs text-slate-400">Exemplos:</span>
        {SAMPLES.map((s) => (
          <button
            key={s.label}
            type="button"
            className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600 hover:bg-slate-200"
            onClick={() => {
              setAssunto(s.assunto);
              setMensagem(s.mensagem);
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      <button
        type="submit"
        disabled={tooShort || loading}
        className="mt-4 flex items-center justify-center gap-2 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Send size={16} /> {loading ? "Classificando…" : "Classificar"}
      </button>
    </form>
  );
}
