export interface NetworkLogEntry {
  timestamp: string;
  method: string;
  url: string;
  status: number;
  durationMs: number;
}

export const networkLogEvents = new EventTarget();
const _networkLog: NetworkLogEntry[] = [];

export function getNetworkLog(): NetworkLogEntry[] {
  return _networkLog;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const start = performance.now();
  const method = init?.method ?? "GET";

  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  const entry: NetworkLogEntry = {
    timestamp: new Date().toISOString(),
    method,
    url: path,
    status: res.status,
    durationMs: Math.round(performance.now() - start),
  };
  _networkLog.push(entry);
  networkLogEvents.dispatchEvent(new CustomEvent("entry", { detail: entry }));

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(detail, res.status, data);
  }

  return data as T;
}
