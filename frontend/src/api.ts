import type {
  DemoScenario,
  DemoStartResponse,
  HealthResponse,
  Incident,
  IncidentListResponse,
  MetricsResponse,
  SessionStatus,
  SystemStatusResponse,
} from "./types";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse failure
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function resolveEvidenceUrl(evidenceUrl: string | null): string | null {
  if (!evidenceUrl) return null;
  if (evidenceUrl.startsWith("http://") || evidenceUrl.startsWith("https://")) return evidenceUrl;
  return `${API_BASE_URL}${evidenceUrl.startsWith("/") ? "" : "/"}${evidenceUrl}`;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  systemStatus: () => request<SystemStatusResponse>("/api/system-status"),
  listIncidents: (limit = 100) => request<IncidentListResponse>(`/api/incidents?limit=${limit}`),
  getIncident: (id: string) => request<Incident>(`/api/incidents/${encodeURIComponent(id)}`),
  approveIncident: (id: string, approver: string, notes?: string) =>
    request<Incident>(`/api/incidents/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ approver, notes }),
    }),
  rejectIncident: (id: string, approver: string, notes?: string) =>
    request<Incident>(`/api/incidents/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body: JSON.stringify({ approver, notes }),
    }),
  demoStart: (scenario: DemoScenario, sessionId: string) =>
    request<DemoStartResponse>("/api/demo/start", {
      method: "POST",
      body: JSON.stringify({ scenario, session_id: sessionId }),
    }),
  demoStop: (sessionId: string) =>
    request<{ session_id: string; status: string }>("/api/demo/stop", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  demoStatus: (sessionId: string) => request<SessionStatus>(`/api/demo/status/${encodeURIComponent(sessionId)}`),
  metrics: () => request<MetricsResponse>("/api/metrics"),
};
