import { apiClient, request } from "./client";
import type { AIActivityEvent, AIAnalysisResponse, AIHealthResponse, AITestResponse } from "../types";

export function getAIHealth(): Promise<AIHealthResponse> {
  return apiClient.get<AIHealthResponse>("/api/ai/health");
}

export function getAIActivity(incidentId?: string): Promise<AIActivityEvent[]> {
  const suffix = incidentId ? `?incident_id=${encodeURIComponent(incidentId)}` : "";
  return apiClient.get<AIActivityEvent[]>(`/api/ai/activity${suffix}`);
}

export function testAI(): Promise<AITestResponse> {
  return request<AITestResponse>("/api/ai/test", {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function analyzeIncident(incidentId: string): Promise<AIAnalysisResponse> {
  return request<AIAnalysisResponse>("/api/ai/analyze", {
    method: "POST",
    body: JSON.stringify({ incident_id: incidentId })
  });
}

export function analyzeScenario(scenarioId: string): Promise<AIAnalysisResponse> {
  return request<AIAnalysisResponse>("/api/ai/analyze", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId })
  });
}
