import { apiClient } from "./client";
import type { ActivityEvent, Incident } from "../types";

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
