import { apiFetch } from "./client";
import type { CreateSessionResponse, Hook, ScenarioKey, SessionDetailResponse, SessionListItem } from "@/types";

export function listSessions(): Promise<SessionListItem[]> {
  return apiFetch("/api/sessions");
}

export function createSession(hook: Hook, scenarioKey: ScenarioKey): Promise<CreateSessionResponse> {
  return apiFetch("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ hook, scenario_key: scenarioKey }),
  });
}

export function getSession(id: string): Promise<SessionDetailResponse> {
  return apiFetch(`/api/sessions/${id}`);
}

export function deleteSession(id: string): Promise<{ status: string }> {
  return apiFetch(`/api/sessions/${id}`, { method: "DELETE" });
}
