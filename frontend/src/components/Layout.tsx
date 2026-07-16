import { NavLink, Outlet } from "react-router-dom";
import { Activity, History, LayoutDashboard } from "lucide-react";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
  }`;

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-600 text-white">
              MT
            </div>
            <span className="font-semibold text-slate-800">Message Triage Agent</span>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink to="/" className={linkClass} end>
              <Activity size={16} /> Classificar
            </NavLink>
            <NavLink to="/dashboard" className={linkClass}>
              <LayoutDashboard size={16} /> Dashboard
            </NavLink>
            <NavLink to="/history" className={linkClass}>
              <History size={16} /> Histórico
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-3 text-xs text-slate-400 flex justify-between">
          <span>Structured LLM triage · v0.1.0</span>
          <a
            className="hover:text-slate-600"
            href="https://github.com/EverFelliphe/message-triage-agent"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
