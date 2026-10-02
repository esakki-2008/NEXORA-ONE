import { apiClient } from "./client";
import type { ScenarioFixture, ScenarioSummary } from "../types";

export function listScenarioSummaries(): Promise<ScenarioSummary[]> {
  return apiClient.get<ScenarioSummary[]>("/api/simulator/scenarios");
}

export function getScenario(scenarioId: string): Promise<ScenarioFixture> {
  return apiClient.get<ScenarioFixture>(
    `/api/simulator/scenarios/${encodeURIComponent(scenarioId)}`
  );
}
