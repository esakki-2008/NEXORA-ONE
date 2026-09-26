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

export type AgentState =
  | "IDLE"
  | "INCIDENT_RECEIVED"
  | "OBSERVING"
  | "INVESTIGATING"
  | "HYPOTHESIS_GENERATED"
  | "VALIDATING"
  | "REMEDIATION_PROPOSED"
  | "WAITING_FOR_APPROVAL"
  | "EXECUTING"
  | "VERIFYING"
  | "RESOLVED"
  | "FAILED"
  | "CANCELLED"
  | "REQUIRES_HUMAN";

export type EvidenceType =
  | "log"
  | "metric"
  | "deployment"
  | "configuration"
  | "transaction"
  | "document"
  | "manual";

export type HypothesisValidationStatus =
  | "unvalidated"
  | "supported"
  | "contradicted"
  | "inconclusive";

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  service: string;
  agent_state: AgentState;
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

export interface Evidence {
  id: string;
  incident_id: string;
  type: EvidenceType;
  source: string;
  timestamp: string;
  summary: string;
  data: Record<string, unknown>;
  relevance: number;
}

export interface Hypothesis {
  id: string;
  incident_id: string;
  title: string;
  description: string;
  confidence: number;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  validation_status: HypothesisValidationStatus;
}

export type IncidentReport = {
  id: string;
  incident_id: string;
  summary: string;
  root_cause: string;
  impact: string;
  timeline: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
  verification: Array<Record<string, unknown>>;
  final_status: IncidentStatus;
  created_at: string;
};

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
}

export interface ScenarioSummary {
  scenario_id: string;
  name: string;
  description: string;
  incident_title: string;
  severity: Severity;
}

export interface ServiceSnapshot {
  name: string;
  status: "healthy" | "degraded" | "down";
  version: string | null;
}

export interface DeploymentSnapshot {
  id: string;
  service: string;
  version: string;
  status: "successful" | "failed" | "rolled_back" | "active";
  deployed_at: string;
  change_summary: string;
}

export interface ConfigurationSnapshot {
  service: string;
  key: string;
  value: unknown;
  expected_value: unknown | null;
  updated_at: string;
  updated_by: string;
}

export interface MetricSnapshot {
  service: string;
  name: string;
  value: number;
  unit: string;
  observed_at: string;
}

export interface LogSnapshot {
  id: string;
  service: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface TransactionSnapshot {
  id: string;
  service: string;
  status: "succeeded" | "failed" | "pending";
  amount: number;
  currency: string;
  timestamp: string;
  failure_reason: string | null;
}

export interface ShopFlowState {
  company: "ShopFlow";
  services: ServiceSnapshot[];
  deployments: DeploymentSnapshot[];
  configurations: ConfigurationSnapshot[];
  metrics: MetricSnapshot[];
  logs: LogSnapshot[];
  transactions: TransactionSnapshot[];
}

export interface ScenarioFixture {
  scenario_id: string;
  name: string;
  description: string;
  incident: {
    scenario_id: string;
    title: string;
    description: string;
    severity: Severity;
    service: string;
    created_at: string;
  };
  state: ShopFlowState;
}

export interface ApiErrorPayload {
  detail?: string;
}
