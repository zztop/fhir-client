import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Banner } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useCreateSession } from "@/hooks/useSession";
import type { Hook, ScenarioKey } from "@/types";

const HOOKS: { value: Hook; label: string; description: string }[] = [
  {
    value: "order-sign",
    label: "Order Signing",
    description: "Signed medication/procedure orders with full clinical context",
  },
  {
    value: "order-select",
    label: "Order Selection",
    description: "Pre-sign selection without authoredOn timestamp",
  },
  {
    value: "appointment-book",
    label: "Appointment Booking",
    description: "Uses FHIR Appointment resource (CPT codes)",
  },
];

const SCENARIOS: { value: ScenarioKey; label: string; code: string; outcome: string }[] = [
  { value: "pa-required", label: "PA Required", code: "RxNorm 1049502", outcome: "PA Required → Granted" },
  {
    value: "pa-not-required",
    label: "PA Not Required",
    code: "CPT 85025",
    outcome: "No Prior Auth Needed",
  },
  {
    value: "auth-pending",
    label: "Auth Pending",
    code: "CPT 33533",
    outcome: "Pended → Granted (via $inquire)",
  },
];

export function NewSession() {
  const [hook, setHook] = useState<Hook | null>(null);
  const [scenarioKey, setScenarioKey] = useState<ScenarioKey | null>(null);
  const navigate = useNavigate();
  const createSession = useCreateSession();

  const handleSubmit = () => {
    if (!hook || !scenarioKey) return;
    createSession.mutate(
      { hook, scenarioKey },
      { onSuccess: (data) => navigate(`/sessions/${data.session.id}`) },
    );
  };

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-xl font-semibold">New Prior Authorization Request</h1>

      {createSession.isError && (
        <Banner tone="error">
          {createSession.error instanceof Error ? createSession.error.message : "Request failed"}
        </Banner>
      )}

      <fieldset>
        <legend className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-200">Hook</legend>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {HOOKS.map((h) => (
            <label
              key={h.value}
              className={`cursor-pointer rounded-lg border p-4 text-sm transition-colors ${
                hook === h.value
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                  : "border-slate-200 hover:border-slate-300 dark:border-slate-800"
              }`}
            >
              <input
                type="radio"
                name="hook"
                className="sr-only"
                checked={hook === h.value}
                onChange={() => setHook(h.value)}
              />
              <p className="font-medium text-slate-900 dark:text-slate-100">{h.label}</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{h.description}</p>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-200">Scenario</legend>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {SCENARIOS.map((s) => (
            <label
              key={s.value}
              className={`cursor-pointer rounded-lg border p-4 text-sm transition-colors ${
                scenarioKey === s.value
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                  : "border-slate-200 hover:border-slate-300 dark:border-slate-800"
              }`}
            >
              <input
                type="radio"
                name="scenario"
                className="sr-only"
                checked={scenarioKey === s.value}
                onChange={() => setScenarioKey(s.value)}
              />
              <p className="font-medium text-slate-900 dark:text-slate-100">{s.label}</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{s.code}</p>
              <p className="mt-2 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {s.outcome}
              </p>
            </label>
          ))}
        </div>
      </fieldset>

      <Button
        className="self-start"
        disabled={!hook || !scenarioKey || createSession.isPending}
        onClick={handleSubmit}
      >
        {createSession.isPending ? "Sending CRD request…" : "Send CRD Request"}
      </Button>
    </div>
  );
}
