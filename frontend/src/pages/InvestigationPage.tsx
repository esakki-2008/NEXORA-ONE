import { useCallback } from "react";
import { Link } from "react-router-dom";

import { listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { IncidentTable } from "../components/IncidentTable";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Incident } from "../types";

export function InvestigationPage() {
  const loader = useCallback(() => listIncidents(), []);
  const { data, isLoading, error, reload } = useAsyncData<Incident[]>(loader);
  if (isLoading && !data) return <LoadingState label="Loading investigation intake…" rows={4} />;
  if (error && !data) return <ErrorState title="Investigation intake unavailable" description={error} onRetry={reload} />;
  const incidents = data ?? [];

  return (
    <section className="page-section">
      <PageHeader eyebrow="INTELLIGENCE / INVESTIGATION" title="Investigation workspace" description="Open an incident to collect provenance-preserving evidence, correlate signals, score hypotheses, and hand off safely to the orchestrator." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh intake</button>} />
      <Panel>
        <SectionHeading eyebrow="INVESTIGATION QUEUE" title="Incident records" description="Investigation collection remains bounded by the Phase 4 allow-list and server-side policy." action={<StatusBadge value="server-owned" label="Server-owned" dot />} />
        {incidents.length ? <IncidentTable incidents={incidents} /> : <EmptyState title="No incidents available for investigation" description="The investigation queue will populate when the incident API receives a record." />}
      </Panel>
      <div className="source-note"><Icon name="shield" size={15} /> Evidence is labeled by source and provenance. No private chain-of-thought or unverified causal claim is displayed.</div>
    </section>
  );
}

export function InvestigationLink({ incidentId }: { incidentId: string }) {
  return <Link className="text-link" to={`/investigation/${incidentId}`}>Open investigation <Icon name="arrow" size={13} /></Link>;
}
