import { apiFetch } from "./client";
import type { AnsweredItem, DTRNextResponse, DTRStartResponse, DTRState, DTRSubmitResponse } from "@/types";

export function startDtr(sessionId: string): Promise<DTRStartResponse> {
  return apiFetch(`/api/sessions/${sessionId}/dtr/start`, { method: "POST" });
}

export function getDtrState(sessionId: string): Promise<DTRState> {
  return apiFetch(`/api/sessions/${sessionId}/dtr`);
}

export function nextQuestion(sessionId: string, item: AnsweredItem): Promise<DTRNextResponse> {
  return apiFetch(`/api/sessions/${sessionId}/dtr/next`, {
    method: "POST",
    body: JSON.stringify(item),
  });
}

export function submitDtr(sessionId: string, items?: AnsweredItem[]): Promise<DTRSubmitResponse> {
  return apiFetch(`/api/sessions/${sessionId}/dtr/submit`, {
    method: "POST",
    body: items ? JSON.stringify({ items }) : undefined,
  });
}
