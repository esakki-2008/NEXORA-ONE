import { apiClient } from "./client";
import type {
  CollectionRequest,
  CorrelationRecord,
  EvidenceRecord,
  InvestigationContext,
  InvestigationSummary,
  InvestigationHypothesis,
  InvestigationTimelineEvent,
  TestHypothesisRequest
} from "../types";

export function listInvestigations(): Promise<InvestigationSummary[]> {
  return apiClient.get<InvestigationSummary[]>("/api/investigations");
}

export function getInvestigationForIncident(incidentId: string): Promise<InvestigationContext> {
  return apiClient.get<InvestigationContext>(
    `/api/investigations/incidents/${encodeURIComponent(incidentId)}`
  );
}

export function getInvestigation(investigationId: string): Promise<InvestigationContext> {
  return apiClient.get<InvestigationContext>(
    `/api/investigations/${encodeURIComponent(investigationId)}`
  );
}

export function getInvestigationSummary(investigationId: string): Promise<InvestigationSummary> {
  return apiClient.get<InvestigationSummary>(
    `/api/investigations/${encodeURIComponent(investigationId)}/summary`
  );
}

export function startInvestigation(
  incidentId: string,
  scenarioId?: string,
  autoHandoff = true
): Promise<InvestigationContext> {
  return apiClient.post<InvestigationContext>(
    `/api/investigations/incidents/${encodeURIComponent(incidentId)}/start`,
    {
      scenario_id: scenarioId || null,
      auto_handoff: autoHandoff
    }
  );
}

export function listInvestigationEvidence(investigationId: string): Promise<EvidenceRecord[]> {
  return apiClient.get<EvidenceRecord[]>(
    `/api/investigations/${encodeURIComponent(investigationId)}/evidence`
  );
}

export function listInvestigationCorrelations(investigationId: string): Promise<CorrelationRecord[]> {
  return apiClient.get<CorrelationRecord[]>(
    `/api/investigations/${encodeURIComponent(investigationId)}/correlations`
  );
}

export function listInvestigationHypotheses(
  investigationId: string
): Promise<InvestigationHypothesis[]> {
  return apiClient.get<InvestigationHypothesis[]>(
    `/api/investigations/${encodeURIComponent(investigationId)}/hypotheses`
  );
}

export function listInvestigationTimeline(
  investigationId: string
): Promise<InvestigationTimelineEvent[]> {
  return apiClient.get<InvestigationTimelineEvent[]>(
    `/api/investigations/${encodeURIComponent(investigationId)}/timeline`
  );
}

export function collectInvestigationEvidence(
  investigationId: string,
  request: CollectionRequest = {}
): Promise<InvestigationContext> {
  return apiClient.post<InvestigationContext>(
    `/api/investigations/${encodeURIComponent(investigationId)}/collect`,
    request
  );
}

export function testInvestigationHypothesis(
  investigationId: string,
  request: TestHypothesisRequest
): Promise<InvestigationContext> {
  return apiClient.post<InvestigationContext>(
    `/api/investigations/${encodeURIComponent(investigationId)}/test-hypothesis`,
    request
  );
}

export function handoffInvestigation(investigationId: string): Promise<InvestigationContext> {
  return apiClient.post<InvestigationContext>(
    `/api/investigations/${encodeURIComponent(investigationId)}/handoff`,
    {}
  );
}
