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
  incident_id: string | null;
  event_type: string;
  message: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AIActivityEvent extends ActivityEvent {}

export type AIHealthStatus =
  | "configured"
  | "not_configured"
  | "authentication_failed"
  | "provider_unavailable"
  | "model_unavailable"
  | "timeout"
  | "error";

export interface AIHealthResponse {
  provider: "nebius";
  model: string;
  status: AIHealthStatus;
  verified: boolean;
  message: string;
  last_verified_at: string | null;
}

export interface AITestResponse {
  success: boolean;
  status: AIHealthStatus;
  message: string;
  response: AIAnalysisResponse | null;
}

export interface AIAnalysisResponse {
  status: string;
  current_step: string;
  summary: string;
  selected_tools: Array<{
    tool_name: string;
    arguments: Record<string, unknown>;
    risk_level: string;
    reason: string;
  }>;
  evidence: Array<{ evidence_id: string; source: string; summary: string }>;
  hypotheses: Array<{
    title: string;
    description: string;
    confidence: number;
    supporting_evidence: string[];
    contradicting_evidence: string[];
    validation_status: string;
  }>;
  validated_hypothesis: string | null;
  recommendation: {
    action: string;
    rationale: string;
    risk_level: string;
    requires_approval: boolean;
  } | null;
  risk_level: string;
  requires_approval: boolean;
  verification_plan: Array<{ check: string; expected_state: Record<string, unknown> }>;
  confidence: number;
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

export type OrchestrationDomain =
  | "IT"
  | "REVENUE"
  | "SUPPORT"
  | "SUPPLY_CHAIN"
  | "CONTRACTS"
  | "CLOUD"
  | "DATA"
  | "COMPLIANCE";

export type OrchestratorRuntimeStatus =
  | "IDLE"
  | "RUNNING"
  | "WAITING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type OrchestrationHypothesisStatus =
  | "PROPOSED"
  | "TESTING"
  | "SUPPORTED"
  | "REJECTED"
  | "INCONCLUSIVE";

export type OrchestrationToolStatus =
  | "SUCCESS"
  | "FAILED"
  | "REJECTED"
  | "TIMEOUT"
  | "NOT_AVAILABLE";

export type RiskLevel = "READ_ONLY" | "LOW" | "MEDIUM" | "HIGH";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "cancelled";
export type VerificationOutcome = "VERIFIED" | "NOT_VERIFIED" | "PARTIALLY_VERIFIED";

export interface OrchestrationActivity {
  id: string;
  incident_id: string;
  event_type: string;
  message: string;
  created_at: string;
  metadata: Record<string, string>;
}

export interface OrchestrationHypothesis {
  id: string;
  title: string;
  description: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  missing_evidence: string[];
  confidence: number;
  status: OrchestrationHypothesisStatus;
}

export interface ToolResultRecord {
  execution_id: string;
  tool_name: string;
  status: OrchestrationToolStatus;
  result: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  timestamp: string;
  risk_level: RiskLevel;
}

export interface RemediationStep {
  id: string;
  sequence: number;
  action: string;
  description: string;
  tool_name: string;
  parameters: Record<string, unknown>;
  risk_level: RiskLevel;
  is_change: boolean;
  requires_approval: boolean;
  status: string;
}

export interface RemediationPlan {
  id: string;
  problem: string;
  steps: RemediationStep[];
  created_at: string;
}

export interface ApprovalRecord {
  approval_id: string;
  incident_id: string;
  action_id: string;
  requested_action: string;
  risk_level: RiskLevel;
  reason: string;
  expected_impact: string;
  rollback_plan: string;
  requested_at: string;
  expires_at: string;
  status: ApprovalStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  decision_reason: string | null;
}

export interface VerificationRecord {
  id: string;
  incident_id: string;
  check: string;
  expected_result: Record<string, unknown>;
  actual_result: Record<string, unknown>;
  status: VerificationOutcome;
  timestamp: string;
}

export interface TransitionRecord {
  from_state: AgentState;
  to_state: AgentState;
  occurred_at: string;
  reason: string | null;
}

export interface OrchestrationContext {
  incident_id: string;
  incident: Incident;
  source_type: string;
  scenario_id: string | null;
  current_state: AgentState;
  runtime_status: OrchestratorRuntimeStatus;
  evidence: Array<{
    id: string;
    source: string;
    timestamp: string;
    type: string;
    summary: string;
    raw_reference: Record<string, string>;
    relevance: number;
  }>;
  hypotheses: OrchestrationHypothesis[];
  selected_domain: OrchestrationDomain | null;
  selected_domains: OrchestrationDomain[];
  selected_agent: string | null;
  tool_calls: Array<{
    id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
    risk_level: RiskLevel;
    reason: string;
    status: string;
    requested_at: string;
  }>;
  tool_results: ToolResultRecord[];
  risk_level: RiskLevel;
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | null;
  priority_factors: Record<string, number>;
  remediation_plan: RemediationPlan | null;
  approval: ApprovalRecord | null;
  verification_plan: string[];
  verification_results: VerificationRecord[];
  verification_outcome: VerificationOutcome | null;
  activity: OrchestrationActivity[];
  transition_history: TransitionRecord[];
  errors: string[];
  analysis_summary: string | null;
  analysis_confidence: number | null;
  ai_status: AIHealthStatus | null;
  created_at: string;
  updated_at: string;
}

export interface OrchestratorSpecialist {
  name: string;
  domain: OrchestrationDomain;
  status: string;
  current_task: string | null;
  last_activity: string | null;
  capabilities: string[];
}

export interface OrchestratorOverview {
  name: string;
  status: OrchestratorRuntimeStatus;
  active_incidents: number;
  specialists: OrchestratorSpecialist[];
  last_activity: string | null;
}

export interface ToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  risk_level: RiskLevel;
  requires_approval: boolean;
  domain: string;
  enabled: boolean;
}

export interface ActionRecord {
  execution_id: string | null;
  action_id: string;
  incident_id: string;
  action: string;
  risk_level: RiskLevel;
  approval_status: ApprovalStatus | null;
  status: OrchestrationToolStatus | string;
  timestamp: string;
  requested_by: string;
  approved_by: string | null;
  result: Record<string, unknown>;
}
