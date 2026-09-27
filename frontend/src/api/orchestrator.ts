import { apiClient } from "./client";
import type {
  ActionRecord,
  ApprovalRecord,
  OrchestrationActivity,
  OrchestrationContext,
  OrchestratorOverview,
  OrchestratorSpecialist,
  ToolDefinition,
  VerificationRecord
} from "../types";

export function getOrchestratorOverview(): Promise<OrchestratorOverview> {
  return apiClient.get<OrchestratorOverview>("/api/orchestrator/overview");
}

export function listOrchestratorAgents(): Promise<OrchestratorSpecialist[]> {
  return apiClient.get<OrchestratorSpecialist[]>("/api/orchestrator/agents");
}

export function listOrchestratorTools(): Promise<ToolDefinition[]> {
  return apiClient.get<ToolDefinition[]>("/api/orchestrator/tools");
}

export function getOrchestrationContext(incidentId: string): Promise<OrchestrationContext> {
  return apiClient.get<OrchestrationContext>(
    `/api/orchestrator/incidents/${encodeURIComponent(incidentId)}`
  );
}

export function listOrchestrationActivity(incidentId: string): Promise<OrchestrationActivity[]> {
  return apiClient.get<OrchestrationActivity[]>(
    `/api/orchestrator/incidents/${encodeURIComponent(incidentId)}/activity`
  );
}

export function startOrchestration(
  incidentId: string,
  scenarioId?: string
): Promise<OrchestrationContext> {
  return apiClient.post<OrchestrationContext>(
    `/api/orchestrator/incidents/${encodeURIComponent(incidentId)}/start`,
    scenarioId ? { scenario_id: scenarioId } : {}
  );
}

export function approveOrchestration(
  approvalId: string,
  decidedBy: string,
  reason?: string
): Promise<OrchestrationContext> {
  return apiClient.post<OrchestrationContext>(
    `/api/orchestrator/approvals/${encodeURIComponent(approvalId)}/approve`,
    { decided_by: decidedBy, reason: reason || null }
  );
}

export function rejectOrchestration(
  approvalId: string,
  decidedBy: string,
  reason?: string
): Promise<OrchestrationContext> {
  return apiClient.post<OrchestrationContext>(
    `/api/orchestrator/approvals/${encodeURIComponent(approvalId)}/reject`,
    { decided_by: decidedBy, reason: reason || null }
  );
}

export function listApprovals(status?: string): Promise<ApprovalRecord[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiClient.get<ApprovalRecord[]>(`/api/orchestrator/approvals${query}`);
}

export function listActions(): Promise<ActionRecord[]> {
  return apiClient.get<ActionRecord[]>("/api/orchestrator/actions");
}

export function listVerifications(): Promise<VerificationRecord[]> {
  return apiClient.get<VerificationRecord[]>("/api/orchestrator/verifications");
}
