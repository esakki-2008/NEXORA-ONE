export type Severity = "low" | "medium" | "high" | "critical";

export type IncidentStatus =
  | "open"
  | "investigating"
  | "remediation_proposed"
  | "resolved"
  | "closed"
  | "failed"
  | "cancelled"
  | "requires_human";

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  service: string;
  agent_state: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityEvent {
  id: string;
  incident_id: string;
  event_type: string;
  message: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
}

export interface ApiErrorPayload {
  detail?: string;
}
