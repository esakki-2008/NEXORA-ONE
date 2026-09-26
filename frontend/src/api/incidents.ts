import { apiClient } from "./client";
import type { ActivityEvent, Evidence, Hypothesis, Incident, IncidentReport } from "../types";

export function listIncidents(): Promise<Incident[]> {
  return apiClient.get<Incident[]>("/api/incidents");
}

export function getIncident(incidentId: string): Promise<Incident> {
  return apiClient.get<Incident>(`/api/incidents/${encodeURIComponent(incidentId)}`);
}

export function listIncidentActivity(incidentId: string): Promise<ActivityEvent[]> {
  return apiClient.get<ActivityEvent[]>(
    `/api/incidents/${encodeURIComponent(incidentId)}/activity`
  );
}

export function listIncidentEvidence(incidentId: string): Promise<Evidence[]> {
  return apiClient.get<Evidence[]>(`/api/incidents/${encodeURIComponent(incidentId)}/evidence`);
}

export function listIncidentHypotheses(incidentId: string): Promise<Hypothesis[]> {
  return apiClient.get<Hypothesis[]>(
    `/api/incidents/${encodeURIComponent(incidentId)}/hypotheses`
  );
}

export function getIncidentReport(incidentId: string): Promise<IncidentReport> {
  return apiClient.get<IncidentReport>(`/api/incidents/${encodeURIComponent(incidentId)}/report`);
}
