export type IncidentType = "fire_smoke" | "person_down" | "route_obstruction";

export type Severity = "NONE" | "LOW" | "MEDIUM" | "HIGH";

export type ActionStatus = "OPEN" | "ACTION_TAKEN" | "CLOSED";

export type ApprovalStatus = "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED";

export interface Incident {
  incident_id: string;
  timestamp: number;
  incident_type: IncidentType;
  severity: Severity;
  confidence: number;
  location: string;
  evidence_url: string | null;
  agent_decision: string;
  agent_rationale: string;
  recommended_action: string;
  action_status: ActionStatus;
  human_approval_required: boolean;
  human_approval_status: ApprovalStatus;
  created_at: number;
  updated_at: number;
}

export interface IncidentListResponse {
  incidents: Incident[];
  count: number;
}

export interface HealthResponse {
  status: string;
  opencv_version: string;
  environment: string;
}

export interface SessionStatus {
  session_id: string;
  scenario: string;
  running: boolean;
  current_interval_seconds: number;
  frames_processed: number;
  last_candidate: {
    event_type: string;
    state: "none" | "possible" | "confirmed";
    confidence: number;
    duration_seconds: number;
    region: string;
    motion_score: number;
    positive_frame_ratio: number;
    evidence_available: boolean;
    signals: Record<string, number>;
  } | null;
  last_decision: {
    severity: string;
    decision: string;
    action: string;
    requires_human_approval: boolean;
    rationale: string;
    action_result: string | null;
    incident_id: string | null;
  } | null;
  last_trace: { state: string; detail: string; timestamp: number }[];
  started_at: number;
  updated_at: number;
}

export interface SystemStatusResponse {
  environment: string;
  storage_backend: string;
  incident_backend: string;
  notification_backend: string;
  active_sessions: SessionStatus[];
}

export interface MetricsResponse {
  total_incidents: number;
  incidents_by_severity: Record<string, number>;
  incidents_by_type: Record<string, number>;
  pending_human_approvals: number;
  active_sessions: number;
}

export interface DemoStartResponse {
  session_id: string;
  scenario: string;
  status: string;
}

export type DemoScenario = "fire_smoke" | "person_down" | "route_obstruction" | "normal";
