import { useCallback } from "react";

import { listIncidents } from "../api/incidents";
import { listScenarioSummaries } from "../api/simulator";
import { DomainHealthCard } from "../components/DomainHealthCard";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Incident, ScenarioSummary } from "../types";

interface BusinessHealthData {
  incidents: Incident[];
  scenarios: ScenarioSummary[];
}

export function BusinessHealthPage() {
  const loader = useCallback(async (): Promise<BusinessHealthData> => {
    const [incidents, scenarios] = await Promise.all([listIncidents(), listScenarioSummaries()]);
    return { incidents, scenarios };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  if (isLoading && !data) return <LoadingState label="Loading business health sources…" rows={4} />;
  if (error && !data) return <ErrorState title="Business health is unavailable" description={error} onRetry={reload} />;

  const incidents = data?.incidents ?? [];
  const activeCount = incidents.filter((incident) => !["resolved", "closed", "cancelled"].includes(incident.status)).length;

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="MONITOR / BUSINESS HEALTH"
        title="Business health"
        description="A single view of connected business domains. Missing telemetry is shown as not configured rather than converted into a health score."
        actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh sources</button>}
      />
      <div className="metric-grid metric-grid-three">
        <div className="metric-card"><span className="eyebrow">LIVE INCIDENT FEED</span><strong>{incidents.length}</strong><span className="muted">Total records returned</span></div>
        <div className="metric-card metric-tone-warning"><span className="eyebrow">ACTIVE ISSUES</span><strong>{activeCount}</strong><span className="muted">Derived from incident status</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">SIMULATOR COVERAGE</span><strong>{data?.scenarios.length ?? "—"}</strong><span className="muted">ShopFlow fixtures</span></div>
      </div>
      <Panel>
        <SectionHeading eyebrow="CONNECTED DOMAINS" title="Enterprise domain health" description="Status is limited to live intake and explicitly connected ShopFlow sources." />
        <DomainHealthCard incidents={incidents} />
      </Panel>
      <div className="source-note"><StatusBadge value="source-boundary" label="Source boundary" /> <span>Revenue, customer, and infrastructure health scores will require domain data adapters in later phases.</span></div>
    </section>
  );
}
