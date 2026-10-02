import { apiClient } from "./client";
import type {
  Phase8VerificationEvidence,
  Phase8VerificationRecord,
  Phase8VerificationSummary,
  Phase8VerificationTimelineEvent,
  VerificationLifecycleStatus
} from "../types";

function query(params: { status?: VerificationLifecycleStatus; incidentId?: string; actionId?: string } = {}) {
  const values = new URLSearchParams();
  if (params.status) values.set("status", params.status);
  if (params.incidentId) values.set("incident_id", params.incidentId);
  if (params.actionId) values.set("action_id", params.actionId);
  const suffix = values.toString();
  return suffix ? `?${suffix}` : "";
}

export function listPhase8Verifications(options: { status?: VerificationLifecycleStatus; incidentId?: string; actionId?: string } = {}) {
  return apiClient.get<Phase8VerificationRecord[]>(`/api/verification${query(options)}`);
}

export function getVerificationSummary() {
  return apiClient.get<Phase8VerificationSummary>("/api/verification/summary");
}

export function getPhase8Verification(verificationId: string) {
  return apiClient.get<Phase8VerificationRecord>(`/api/verification/${encodeURIComponent(verificationId)}`);
}

export function runVerification(verificationId: string, requestedBy = "Local operator") {
  return apiClient.post<Phase8VerificationRecord>(
    `/api/verification/${encodeURIComponent(verificationId)}/run`,
    { requested_by: requestedBy }
  );
}

export function retryVerification(verificationId: string, requestedBy = "Local operator", reason?: string) {
  return apiClient.post<Phase8VerificationRecord>(
    `/api/verification/${encodeURIComponent(verificationId)}/retry`,
    { requested_by: requestedBy, reason: reason || null }
  );
}

export function cancelVerification(verificationId: string, requestedBy: string, reason?: string) {
  return apiClient.post<Phase8VerificationRecord>(
    `/api/verification/${encodeURIComponent(verificationId)}/cancel`,
    { requested_by: requestedBy, reason: reason || null }
  );
}

export function getVerificationEvidence(verificationId: string) {
  return apiClient.get<Phase8VerificationEvidence[]>(
    `/api/verification/${encodeURIComponent(verificationId)}/evidence`
  );
}

export function getVerificationTimeline(verificationId: string) {
  return apiClient.get<Phase8VerificationTimelineEvent[]>(
    `/api/verification/${encodeURIComponent(verificationId)}/timeline`
  );
}
