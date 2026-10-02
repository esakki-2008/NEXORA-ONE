import { apiClient } from "./client";
import type {
  ActionAuditEvent,
  ActionCancelRequest,
  ActionDecisionRequest,
  ActionRegistryDefinition,
  ActionRejectRequest,
  ControlledAction,
  ControlledActionCreateRequest,
  ControlledActionVerification
} from "../types";

export function listActions(status?: string): Promise<ControlledAction[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiClient.get<ControlledAction[]>(`/api/actions${query}`);
}

export function getActionRegistry(): Promise<ActionRegistryDefinition[]> {
  return apiClient.get<ActionRegistryDefinition[]>("/api/actions/registry");
}

export function createAction(request: ControlledActionCreateRequest): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>("/api/actions", request);
}

export function getAction(actionId: string): Promise<ControlledAction> {
  return apiClient.get<ControlledAction>(`/api/actions/${encodeURIComponent(actionId)}`);
}

export function approveAction(
  actionId: string,
  request: ActionDecisionRequest
): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>(
    `/api/actions/${encodeURIComponent(actionId)}/approve`,
    request
  );
}

export function rejectAction(
  actionId: string,
  request: ActionRejectRequest
): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>(
    `/api/actions/${encodeURIComponent(actionId)}/reject`,
    request
  );
}

export function executeAction(
  actionId: string,
  request: ActionDecisionRequest
): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>(
    `/api/actions/${encodeURIComponent(actionId)}/execute`,
    request
  );
}

export function cancelAction(
  actionId: string,
  request: ActionCancelRequest
): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>(
    `/api/actions/${encodeURIComponent(actionId)}/cancel`,
    request
  );
}

export function rollbackAction(
  actionId: string,
  request: ActionDecisionRequest
): Promise<ControlledAction> {
  return apiClient.post<ControlledAction>(
    `/api/actions/${encodeURIComponent(actionId)}/rollback`,
    request
  );
}

export function getActionAudit(actionId: string): Promise<ActionAuditEvent[]> {
  return apiClient.get<ActionAuditEvent[]>(
    `/api/actions/${encodeURIComponent(actionId)}/audit`
  );
}

export function getActionVerification(actionId: string): Promise<ControlledActionVerification> {
  return apiClient.get<ControlledActionVerification>(
    `/api/actions/${encodeURIComponent(actionId)}/verification`
  );
}
