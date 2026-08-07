import { apiFetch } from "./client";
import type { HealthStatus, HookInfo, Scenario } from "@/types";

export function getHealth(): Promise<HealthStatus> {
  return apiFetch("/api/health");
}

export function listScenarios(): Promise<Scenario[]> {
  return apiFetch("/api/scenarios");
}

export function listHooks(): Promise<HookInfo[]> {
  return apiFetch("/api/hooks");
}

export function bootstrap(): Promise<{ status: string; fixture_ids: Record<string, string> }> {
  return apiFetch("/api/bootstrap", { method: "POST" });
}
