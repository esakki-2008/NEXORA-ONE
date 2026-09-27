import { apiClient } from "./client";
import type {
  BusinessImpact,
  CrossDomainCorrelation,
  DomainDetail,
  DomainHealth,
  InvestigationLaunch,
  InvestigateSignalRequest,
  OperationalSignal,
  OperationalSnapshot,
  OperationsDomain,
  OperationsHealth,
  PriorityItem
} from "../types";

function query(params: { scenarioId?: string; incidentId?: string; domain?: OperationsDomain } = {}) {
  const values = new URLSearchParams();
  if (params.scenarioId) values.set("scenario_id", params.scenarioId);
  if (params.incidentId) values.set("incident_id", params.incidentId);
  if (params.domain) values.set("domain", params.domain);
  const suffix = values.toString();
  return suffix ? `?${suffix}` : "";
}

function arrayOrEmpty<T>(value: T[] | unknown): T[] {
  return Array.isArray(value) ? value : [];
}

export async function getOperationsSnapshot(options: { scenarioId?: string; incidentId?: string } = {}) {
  const value = await apiClient.get<OperationalSnapshot | unknown>(
    `/api/operations/snapshot${query(options)}`
  );
  return Array.isArray(value) ? null : (value as OperationalSnapshot);
}

export async function refreshOperationsSnapshot(options: { scenarioId?: string; incidentId?: string } = {}) {
  return apiClient.post<OperationalSnapshot>(`/api/operations/refresh${query(options)}`, {});
}

export async function listOperationDomains(options: { scenarioId?: string; incidentId?: string } = {}) {
  const value = await apiClient.get<DomainHealth[] | unknown>(`/api/operations/domains${query(options)}`);
  return arrayOrEmpty<DomainHealth>(value);
}

export async function getOperationDomain(
  domain: OperationsDomain,
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  const value = await apiClient.get<DomainDetail | unknown>(
    `/api/operations/domains/${domain}${query(options)}`
  );
  return Array.isArray(value) ? null : (value as DomainDetail);
}

export async function listOperationalSignals(
  options: { scenarioId?: string; incidentId?: string; domain?: OperationsDomain } = {}
) {
  const value = await apiClient.get<OperationalSignal[] | unknown>(
    `/api/operations/signals${query(options)}`
  );
  return arrayOrEmpty<OperationalSignal>(value);
}

export async function getOperationalSignal(
  signalId: string,
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  return apiClient.get<OperationalSignal>(`/api/operations/signals/${signalId}${query(options)}`);
}

export async function investigateOperationalSignal(
  signalId: string,
  request: InvestigateSignalRequest
) {
  return apiClient.post<InvestigationLaunch>(
    `/api/operations/signals/${signalId}/investigate`,
    request
  );
}

export async function listOperationCorrelations(
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  const value = await apiClient.get<CrossDomainCorrelation[] | unknown>(
    `/api/operations/correlations${query(options)}`
  );
  return arrayOrEmpty<CrossDomainCorrelation>(value);
}

export async function listOperationPriorities(
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  const value = await apiClient.get<PriorityItem[] | unknown>(
    `/api/operations/priorities${query(options)}`
  );
  return arrayOrEmpty<PriorityItem>(value);
}

export async function getOperationsImpact(
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  return apiClient.get<BusinessImpact>(`/api/operations/business-impact${query(options)}`);
}

export async function getOperationsHealth(
  options: { scenarioId?: string; incidentId?: string } = {}
) {
  return apiClient.get<OperationsHealth>(`/api/operations/health${query(options)}`);
}
