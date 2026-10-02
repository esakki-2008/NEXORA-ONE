import { useCallback, useMemo, useState } from "react";

import { listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { IncidentTable } from "../components/IncidentTable";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Incident, IncidentStatus, Severity } from "../types";

export function HistoryPage() {
  const loader = useCallback(() => listIncidents(), []);
  const { data, isLoading, error, reload } = useAsyncData<Incident[]>(loader);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<IncidentStatus | "all">("all");
  const [service, setService] = useState("all");
  const incidents = data ?? [];
  const services = useMemo(() => [...new Set(incidents.map((incident) => incident.service))].sort(), [incidents]);
  const filtered = incidents.filter((incident) => (severity === "all" || incident.severity === severity) && (status === "all" || incident.status === status) && (service === "all" || incident.service === service));

  if (isLoading && !data) return <LoadingState label="Loading incident history…" rows={5} />;
  if (error && !data) return <ErrorState title="History unavailable" description={error} onRetry={reload} />;

  return (
    <section className="page-section">
      <PageHeader eyebrow="REPORTING / HISTORY" title="Incident history" description="Historical tracking uses the records currently returned by the incident API. No historical record is synthesized." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh history</button>} />
      <Panel>
        <SectionHeading eyebrow="FILTERS" title={`${filtered.length} records in view`} description="Filter by the fields available in Phase 1 incident records." />
        <div className="filter-bar history-filters"><label><span className="sr-only">Filter by severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value as Severity | "all")}><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label><label><span className="sr-only">Filter by status</span><select value={status} onChange={(event) => setStatus(event.target.value as IncidentStatus | "all")}><option value="all">All statuses</option><option value="resolved">Resolved</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option><option value="requires_human">Requires human</option><option value="open">Open</option></select></label><label><span className="sr-only">Filter by service</span><select value={service} onChange={(event) => setService(event.target.value)}><option value="all">All services</option>{services.map((item) => <option value={item} key={item}>{item}</option>)}</select></label></div>
        {filtered.length ? <IncidentTable incidents={filtered} compact /> : <EmptyState title={incidents.length ? "No records match these filters" : "No incident history"} description={incidents.length ? "Adjust the filters to view other records." : "Resolved, failed, cancelled, and human-review records will appear after they are recorded by the API."} />}
      </Panel>
    </section>
  );
}
