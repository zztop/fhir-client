import { apiFetch } from "./client";
import type { PASBundle, PASBundleEdits, PASResult } from "@/types";

export function preparePas(sessionId: string): Promise<{ id: string; bundle: PASBundle }> {
  return apiFetch(`/api/sessions/${sessionId}/pas/prepare`, { method: "POST" });
}

export function getPasBundle(sessionId: string): Promise<{ bundle: PASBundle }> {
  return apiFetch(`/api/sessions/${sessionId}/pas/bundle`);
}

export function patchPasBundle(sessionId: string, edits: PASBundleEdits): Promise<{ bundle: PASBundle }> {
  return apiFetch(`/api/sessions/${sessionId}/pas/bundle`, {
    method: "PATCH",
    body: JSON.stringify(edits),
  });
}

export function submitPas(sessionId: string): Promise<PASResult> {
  return apiFetch(`/api/sessions/${sessionId}/pas/submit`, { method: "POST" });
}

export function inquirePas(sessionId: string): Promise<PASResult> {
  return apiFetch(`/api/sessions/${sessionId}/pas/inquire`, { method: "POST" });
}
