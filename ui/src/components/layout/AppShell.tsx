import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { NetworkLog } from "@/components/shared/NetworkLog";
import { Switch } from "@/components/ui/switch";
import { useDevMode } from "@/context/DevModeContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { devMode, setDevMode } = useDevMode();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold">
            FHIR Prior Auth
          </Link>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
            <span>Dev Mode</span>
            <Switch checked={devMode} onCheckedChange={setDevMode} aria-label="Toggle dev mode" />
          </label>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {children}
        {devMode && <NetworkLog />}
      </main>
    </div>
  );
}
