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

export type InvestigationStatus =
  | "CREATED"
  | "COLLECTING"
  | "ANALYZING"
  | "COMPLETED"
  | "INCONCLUSIVE"
  | "REQUIRES_HUMAN"
  | "FAILED"
  | "CANCELLED";

export type InvestigationEvidenceType =
  | "LOG"
  | "METRIC"
  | "DEPLOYMENT"
  | "CONFIGURATION"
  | "HEALTH_CHECK"
  | "TRANSACTION"
  | "DOCUMENTATION"
  | "TEST_RESULT"
  | "ALERT"
  | "CUSTOMER_SIGNAL"
  | "SYSTEM_EVENT";

export type EvidenceCollectionStatus = "COLLECTED" | "FAILED" | "NOT_AVAILABLE" | "REJECTED";
export type InvestigationHypothesisStatus =
  | "PROPOSED"
  | "TESTING"
  | "SUPPORTED"
  | "REJECTED"
  | "INCONCLUSIVE";
export type InvestigationHandoffStatus =
  | "NOT_READY"
  | "READY"
  | "HANDED_OFF"
  | "REQUIRES_HUMAN"
  | "FAILED";

export interface EvidenceRecord {
  evidence_id: string;
  incident_id: string;
  source: string;
  evidence_type: InvestigationEvidenceType;
  timestamp: string;
  summary: string;
  raw_reference: Record<string, string>;
  relevance: number;
  confidence: number;
  collected_by: string;
  collection_status: EvidenceCollectionStatus;
  metadata: Record<string, string>;
  simulated: boolean;
}

export interface CorrelationRecord {
  correlation_id: string;
  incident_id: string;
  evidence_ids: string[];
  relationship: string;
  reason: string;
  dimensions: string[];
  strength: number;
  temporal_delta_seconds: number | null;
  created_at: string;
}

export interface InvestigationHypothesis {
  hypothesis_id: string;
  incident_id: string;
  title: string;
  description: string;
  domain: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  missing_evidence: string[];
  confidence: number;
  confidence_factors: Record<string, number>;
  status: InvestigationHypothesisStatus;
  priority: string;
  next_validation_step: string | null;
  created_at: string;
  updated_at: string;
}

export interface RootCauseCandidate {
  candidate_id: string;
  hypothesis_id: string;
  title: string;
  summary: string;
  confidence: number;
  evidence_ids: string[];
  qualification: string;
}

export interface InvestigationTimelineEvent {
  event_id: string;
  incident_id: string;
  event_type: string;
  timestamp: string;
  actor: string;
  summary: string;
  related_evidence_ids: string[];
  status: string;
}

export interface InvestigationHandoff {
  status: InvestigationHandoffStatus;
  orchestrator_state: AgentState | null;
  message: string | null;
  handed_off_at: string | null;
}

export interface InvestigationContext {
  investigation_id: string;
  incident_id: string;
  incident: Incident;
  source_type: string;
  scenario_id: string | null;
  status: InvestigationStatus;
  evidence: EvidenceRecord[];
  correlations: CorrelationRecord[];
  hypotheses: InvestigationHypothesis[];
  selected_hypothesis: string | null;
  evidence_gaps: string[];
  recommended_next_step: string | null;
  confidence: number;
  confidence_factors: Record<string, number>;
  confidence_explanation: string[];
  root_cause_candidates: RootCauseCandidate[];
  timeline: InvestigationTimelineEvent[];
  errors: string[];
  ai_status: AIHealthStatus | null;
  ai_summary: string | null;
  orchestrator_handoff: InvestigationHandoff;
  request_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationSummary {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  source_type: string;
  evidence_count: number;
  correlation_count: number;
  hypothesis_count: number;
  confidence: number;
  selected_hypothesis: string | null;
  recommended_next_step: string | null;
  orchestrator_handoff: InvestigationHandoff;
  updated_at: string;
}

export interface CollectionRequest {
  tool_names?: string[];
}

export interface TestHypothesisRequest {
  hypothesis_id: string;
  tool_names?: string[];
}

export type OperationsDomain =
  | "IT"
  | "REVENUE"
  | "SUPPORT"
  | "SUPPLY_CHAIN"
  | "CONTRACTS"
  | "CLOUD"
  | "DATA"
  | "COMPLIANCE";

export type DomainHealthStatus =
  | "HEALTHY"
  | "DEGRADED"
  | "WARNING"
  | "CRITICAL"
  | "UNKNOWN"
  | "NOT_CONFIGURED";

export type OperationalSignalStatus = "ACTIVE" | "WATCH" | "INFO" | "RESOLVED";
export type OperationsPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type OperationsImpactLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type OperationsRelationshipType =
  | "TEMPORAL"
  | "SERVICE_DEPENDENCY"
  | "BUSINESS_IMPACT"
  | "SHARED_RESOURCE"
  | "SHARED_IDENTIFIER"
  | "POSSIBLE_CAUSAL"
  | "UNKNOWN";
export type OperationsSourceType =
  | "SIMULATOR"
  | "INCIDENT_SYSTEM"
  | "MONITORING"
  | "PAYMENT_SYSTEM"
  | "SUPPORT_SYSTEM"
  | "INVENTORY_SYSTEM"
  | "CONTRACT_SYSTEM"
  | "CLOUD_SYSTEM"
  | "DATA_PIPELINE"
  | "COMPLIANCE_SYSTEM"
  | "NOT_CONFIGURED";
export type OperationsSourceAvailability =
  | "AVAILABLE"
  | "PARTIAL"
  | "NOT_CONFIGURED"
  | "FAILED";

export interface OperationsSourceMetadata {
  source_type: OperationsSourceType;
  source_name: string;
  label: string;
  collected_at: string;
  availability: OperationsSourceAvailability;
  simulator: boolean;
}

export interface OperationsSourceStatus {
  domain: OperationsDomain;
  source_type: OperationsSourceType;
  source_name: string;
  status: OperationsSourceAvailability;
  message: string;
  last_updated: string | null;
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export interface BusinessImpactSummary {
  impact_level: OperationsImpactLevel;
  affected_customers: number | null;
  estimated_revenue_impact: number | null;
  currency: string | null;
  explanation: string;
  source: OperationsSourceMetadata;
  simulator: boolean;
}

export interface BusinessMetric {
  metric_id: string;
  domain: OperationsDomain;
  name: string;
  value: number;
  unit: string;
  baseline: number | null;
  delta: number | null;
  observed_at: string;
  source: OperationsSourceMetadata;
  simulator: boolean;
}

export interface ServiceHealth {
  service: string;
  status: "HEALTHY" | "DEGRADED" | "DOWN" | "UNKNOWN";
  health_score: number | null;
  latency_ms: number | null;
  error_rate: number | null;
  observed_at: string | null;
  source: OperationsSourceMetadata;
  simulator: boolean;
}

export interface OperationalSignal {
  signal_id: string;
  domain: OperationsDomain;
  kind: string;
  title: string;
  summary: string;
  status: OperationalSignalStatus;
  severity: Severity;
  priority: OperationsPriority;
  observed_at: string;
  related_service: string | null;
  related_incident_id: string | null;
  evidence_ids: string[];
  metrics: Record<string, number>;
  business_impact: BusinessImpactSummary | null;
  source: OperationsSourceMetadata;
  simulator: boolean;
  impact_relevant: boolean;
  metric_name?: string;
  metric_value?: number;
  currency?: string | null;
  estimated?: boolean;
  affected_customers?: number;
  issue_category?: string;
  sentiment?: number | null;
  risk_status?: "NORMAL" | "WATCH" | "AT_RISK" | "CRITICAL";
  contract_status?: string;
  days_remaining?: number | null;
  vendor?: string;
  utilization?: number | null;
  estimated_cost?: number | null;
  quality_metric?: string;
  quality_value?: number;
  dataset?: string;
  compliance_status?: string;
  control?: string;
}

export interface DomainHealth {
  domain: OperationsDomain;
  status: DomainHealthStatus;
  health_score: number | null;
  active_signals: string[];
  critical_signals: string[];
  business_impact: BusinessImpactSummary;
  last_updated: string | null;
  source: OperationsSourceMetadata;
  simulator: boolean;
  service_health: ServiceHealth[];
}

export interface CrossDomainCorrelation {
  correlation_id: string;
  source_domain: OperationsDomain;
  target_domain: OperationsDomain;
  source_signal: string;
  target_signal: string;
  relationship_type: OperationsRelationshipType;
  temporal_relationship: string;
  confidence: number;
  explanation: string;
  evidence_ids: string[];
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export interface BusinessImpact {
  impact_level: OperationsImpactLevel;
  affected_domains: OperationsDomain[];
  affected_services: string[];
  estimated_customer_impact: number | null;
  estimated_revenue_impact: number | null;
  currency: string | null;
  operational_scope: string;
  duration_minutes: number | null;
  explanation: string[];
  source: OperationsSourceMetadata;
  simulator: boolean;
}

export interface PriorityItem {
  priority_id: string;
  signal_id: string;
  domain: OperationsDomain;
  title: string;
  priority: OperationsPriority;
  score: number;
  factors: Record<string, number>;
  explanation: string;
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export interface OperationalEvent {
  event_id: string;
  event_type: string;
  summary: string;
  timestamp: string;
  related_signal_ids: string[];
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export interface OperationalSnapshot {
  timestamp: string;
  overall_status: DomainHealthStatus;
  domains: DomainHealth[];
  critical_signals: OperationalSignal[];
  business_impact: BusinessImpact;
  cross_domain_correlations: CrossDomainCorrelation[];
  priority_items: PriorityItem[];
  recent_events: OperationalEvent[];
  source_status: OperationsSourceStatus[];
  scenario_id: string | null;
  incident_id: string | null;
  simulator: boolean;
  source: OperationsSourceMetadata;
  refresh_id: string;
}

export interface DomainDetail {
  health: DomainHealth;
  metrics: BusinessMetric[];
  signals: OperationalSignal[];
  related_incidents: string[];
  related_evidence_ids: string[];
  correlations: CrossDomainCorrelation[];
  business_impact: BusinessImpact;
  recommended_investigation: string | null;
  source_status: OperationsSourceStatus;
  simulator: boolean;
}

export interface OperationsHealth {
  status: OperationsSourceAvailability;
  timestamp: string;
  configured_domains: OperationsDomain[];
  not_configured_domains: OperationsDomain[];
  source_status: OperationsSourceStatus[];
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export interface InvestigateSignalRequest {
  scenario_id?: string;
  request_id?: string;
  auto_handoff?: boolean;
}

export interface InvestigationLaunch {
  signal_id: string;
  incident_id: string;
  investigation_id: string;
  investigation_status: string;
  message: string;
  scenario_id: string | null;
  simulator: boolean;
  source: OperationsSourceMetadata;
}

export type ControlledActionStatus =
  | "PROPOSED"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "EXECUTING"
  | "COMPLETED"
  | "FAILED"
  | "ROLLED_BACK"
  | "CANCELLED"
  | "REQUIRES_HUMAN";
export type ControlledActionVerificationState =
  | "PENDING"
  | "RUNNING"
  | "PASSED"
  | "FAILED"
  | "REQUIRES_HUMAN";
export type ControlledActionApprovalState =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED";

export interface ControlledAction {
  action_id: string;
  incident_id: string;
  action_name: string;
  normalized_parameters: Record<string, unknown>;
  risk_level: RiskLevel;
  expected_impact: string;
  rollback_plan: string;
  status: ControlledActionStatus;
  created_at: string;
  updated_at: string;
  requested_by: string;
  approved_by: string | null;
  approval_id: string | null;
  approval_status: ControlledActionApprovalState | null;
  action_fingerprint: string;
  idempotency_key: string;
  execution_attempts: number;
  verification_status: ControlledActionVerificationState;
  rollback_verification_status: ControlledActionVerificationState | null;
  failure_reason: string | null;
  audit_reference: string;
  rollback_supported: boolean;
  rollback_action: string | null;
  rollback_parameters: Record<string, unknown>;
  rollback_conditions: string[];
  verification_strategy: string;
  scenario_id: string | null;
  evidence_ids: string[];
  planning_summary: string;
  execution_before_state: Record<string, unknown>;
  execution_after_state: Record<string, unknown>;
  execution_result: Record<string, unknown>;
}

export interface ActionRegistryDefinition {
  name: string;
  description: string;
  parameter_schema: Record<string, unknown>;
  risk_level: RiskLevel;
  allowed_domains: string[];
  expected_impact: string;
  rollback_supported: boolean;
  verification_strategy: string;
  authorization_requirements: string[];
  rollback_action: string | null;
  rollback_conditions: string[];
}

export interface ControlledActionCreateRequest {
  incident_id: string;
  investigation_id?: string | null;
  scenario_id?: string | null;
  action_name?: string | null;
  recommended_action?: string | null;
  parameters?: Record<string, unknown>;
  root_cause_candidate?: string | null;
  requested_by: string;
  idempotency_key?: string | null;
}

export interface ActionDecisionRequest {
  requested_by: string;
  reason?: string | null;
  auto_execute?: boolean;
}

export interface ActionRejectRequest {
  requested_by: string;
  reason: string;
}

export interface ActionCancelRequest {
  requested_by: string;
  reason?: string | null;
}

export type ActionAuditEventType =
  | "action.created"
  | "action.approval.requested"
  | "action.approved"
  | "action.rejected"
  | "action.expired"
  | "action.execution.started"
  | "action.execution.completed"
  | "action.execution.failed"
  | "action.verification.started"
  | "action.verification.completed"
  | "action.rollback.started"
  | "action.rollback.completed"
  | "action.human.escalation"
  | "action.cancelled"
  | "action.incident.resolved";

export interface ActionAuditEvent {
  event_id: string;
  action_id: string;
  incident_id: string;
  event_type: ActionAuditEventType;
  actor: string;
  timestamp: string;
  message: string;
  metadata: Record<string, string>;
  previous_hash: string;
  event_hash: string;
}

export interface ControlledActionVerification {
  action_id: string;
  incident_id: string;
  status: ControlledActionVerificationState;
  details: string;
  verification_strategy: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  rollback_status: ControlledActionVerificationState | null;
  timestamp: string;
}
