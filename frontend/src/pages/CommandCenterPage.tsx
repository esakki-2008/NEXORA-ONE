import { useCallback } from "react";

import { getAIActivity, getAIHealth } from "../api/ai";
import { getOrchestratorOverview } from "../api/orchestrator";
import { getHealth } from "../api/health";
import { listIncidentActivity, listIncidents } from "../api/incidents";
import { listScenarioSummaries } from "../api/simulator";
import { ActivityTimeline } from "../components/ActivityTimeline";
import { DomainHealthCard } from "../components/DomainHealthCard";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { IncidentTable } from "../components/IncidentTable";
import { LoadingState } from "../components/LoadingState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime } from "../lib/format";
import type { ActivityEvent, AIHealthResponse, HealthResponse, Incident, OrchestratorOverview, ScenarioSummary } from "../types";

interface CommandCenterData {
  incidents: Incident[];
  activity: ActivityEvent[];
  scenarios: ScenarioSummary[] | null;
  health: HealthResponse | null;
  aiHealth: AIHealthResponse | null;
  orchestrator: OrchestratorOverview | null;
}

async function loadCommandCenter(): Promise<CommandCenterData> {
  const [healthResult, incidentsResult, scenariosResult, aiHealthResult, aiActivityResult, orchestratorResult] = await Promise.allSettled([
    getHealth(),
    listIncidents(),
    listScenarioSummaries(),
    getAIHealth(),
    getAIActivity(),
    getOrchestratorOverview()
  ]);

  if (incidentsResult.status === "rejected") throw incidentsResult.reason;
  const incidents = incidentsResult.value;
  const activityResults = await Promise.all(
    incidents.slice(0, 12).map(async (incident) => {
      try {
        return await listIncidentActivity(incident.id);
      } catch {
        return [];
      }
    })
  );

  const activity = [
    ...(aiActivityResult.status === "fulfilled" ? aiActivityResult.value : []),
    ...activityResults.flat()
  ].sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());

  return {
    incidents,
    activity,
    scenarios: scenariosResult.status === "fulfilled" ? scenariosResult.value : null,
    health: healthResult.status === "fulfilled" ? healthResult.value : null,
    aiHealth: aiHealthResult.status === "fulfilled" && !Array.isArray(aiHealthResult.value) ? aiHealthResult.value : null,
    orchestrator: orchestratorResult.status === "fulfilled" && !Array.isArray(orchestratorResult.value) ? orchestratorResult.value : null
  };
}

export function CommandCenterPage() {
  const loader = useCallback(() => loadCommandCenter(), []);
  const { data, isLoading, error, updatedAt, reload } = useAsyncData(loader);

  if (isLoading && !data) {
    return <LoadingState label="Loading enterprise command center…" rows={5} />;
  }

  if (error && !data) {
    return <ErrorState title="Unable to load command center" description={error} onRetry={reload} />;
  }

  const incidents = data?.incidents ?? [];
  const activeIncidents = incidents.filter((incident) => !["resolved", "closed", "cancelled"].includes(incident.status));
  const criticalCount = activeIncidents.filter((incident) => incident.severity === "critical").length;
  const scenarioCount = data?.scenarios?.length ?? null;
  const aiStatusLabel = data?.aiHealth?.verified
    ? "CONNECTED"
    : data?.aiHealth?.status === "not_configured"
      ? "NOT CONFIGURED"
      : data?.aiHealth?.status === "provider_unavailable"
        ? "PROVIDER UNAVAILABLE"
        : data?.aiHealth?.status === "authentication_failed"
          ? "AUTHENTICATION FAILED"
          : data?.aiHealth?.status === "model_unavailable"
            ? "MODEL UNAVAILABLE"
            : "NOT VERIFIED";

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="NEXORA ONE / COMMAND CENTER"
        title="Enterprise Operations Command Center"
        description="AI-powered operational visibility across your business, grounded in the records and simulator sources currently connected."
        meta={<><Icon name="clock" size={13} /> Last updated {updatedAt ? formatDateTime(updatedAt) : "not available"} <span className="meta-separator">·</span> Phase 2 data surface</>}
        actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> {isLoading ? "Refreshing…" : "Refresh command center"}</button>}
      />

      {error ? <div className="inline-alert"><Icon name="incidents" size={15} /> Some optional sources could not be loaded. Values below remain limited to successful responses.</div> : null}

      <div className="metric-grid metric-grid-command">
        <MetricCard label="Active incidents" value={activeIncidents.length} detail="Live incident intake" tone={activeIncidents.length ? "warning" : "success"} icon={<Icon name="incidents" size={16} />} />
        <MetricCard label="Critical issues" value={criticalCount} detail="Recorded critical severity" tone={criticalCount ? "critical" : "default"} icon={<Icon name="activity" size={16} />} />
        <MetricCard label="ShopFlow scenarios" value={scenarioCount ?? "—"} detail={scenarioCount === null ? "Simulator unavailable" : "Structured fixtures available"} tone="info" icon={<Icon name="layers" size={16} />} />
        <MetricCard label="Business health" value="NOT SCORED" detail="No domain telemetry in Phase 2" tone="default" icon={<Icon name="business" size={16} />} />
      </div>

      <Panel>
        <SectionHeading eyebrow="CENTRAL ORCHESTRATOR" title="Response coordination" description="The Command Center reads server-owned orchestration status without inferring activity from missing records." action={<StatusBadge value={data?.orchestrator?.status ?? "not-available"} label={data?.orchestrator ? data.orchestrator.status : "Not available"} dot />} />
        <div className="orchestration-summary"><div><span>Status</span><strong>{data?.orchestrator ? data.orchestrator.status : "Not recorded"}</strong></div><div><span>Active incidents</span><strong>{data?.orchestrator ? data.orchestrator.active_incidents : "—"}</strong></div><div><span>Specialists</span><strong>{data?.orchestrator ? data.orchestrator.specialists.length : "—"}</strong></div><div><span>Last activity</span><strong>{data?.orchestrator?.last_activity ? formatDateTime(data.orchestrator.last_activity) : "Not recorded"}</strong></div></div>
      </Panel>

      <div className="command-grid command-grid-primary">
        <Panel className="panel-span-two">
          <SectionHeading
            eyebrow="LIVE INTAKE"
            title="Active incidents"
            description="Only incidents returned by the Phase 1 API are shown as active operational records."
            action={<StatusBadge value="api-backed" label="API-backed" dot />}
          />
          {activeIncidents.length ? <IncidentTable incidents={activeIncidents} /> : <EmptyState title="No active incidents" description="NEXORA has not received an active incident record from the connected API." compact />}
        </Panel>
        <Panel>
          <SectionHeading eyebrow="OBSERVABLE ACTIVITY" title="AI activity" description="Concise backend events only. Private model reasoning is never displayed." action={<StatusBadge value={aiStatusLabel.toLowerCase().replace(/ /g, "-")} label={`AI ${aiStatusLabel}`} dot />} />
          <ActivityTimeline events={data?.activity ?? []} compact />
        </Panel>
      </div>

      <Panel className="domain-panel">
        <SectionHeading eyebrow="ENTERPRISE HEALTH" title="Business domain health" description="A domain is marked as not configured when Phase 2 has no connected source for it. No health score is inferred from missing data." />
        <DomainHealthCard incidents={incidents} />
      </Panel>

      <Panel>
        <SectionHeading eyebrow="STRUCTURED DEMO SOURCE" title="ShopFlow simulator coverage" description="Synthetic observations are clearly separated from live incident records and do not create incidents." />
        {data?.scenarios?.length ? (
          <div className="scenario-grid">
            {data.scenarios.map((scenario) => (
              <div className="scenario-row" key={scenario.scenario_id}>
                <div><StatusBadge value={scenario.severity} dot /><strong>{scenario.name}</strong></div>
                <span>{scenario.description}</span>
                <span className="muted scenario-source">Synthetic/demo data · simulator fixture</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState compact eyebrow="SIMULATOR UNAVAILABLE" title="No simulator fixtures returned" description="The command center cannot show ShopFlow scenario coverage until the simulator API responds." />
        )}
      </Panel>
    </section>
  );
}
