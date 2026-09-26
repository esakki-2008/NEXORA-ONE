import { useCallback, useEffect, useMemo, useState } from "react";

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
import type { Incident, IncidentStatus, Severity } from "../types";

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<IncidentStatus | "all">("all");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listIncidents()
      .then(setIncidents)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load incidents"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);

  const services = useMemo(() => [...new Set(incidents.map((incident) => incident.service))].sort(), [incidents]);
  const [service, setService] = useState("all");
  const filtered = incidents.filter((incident) => {
    const matchesQuery = `${incident.title} ${incident.description} ${incident.service}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (severity === "all" || incident.severity === severity) && (status === "all" || incident.status === status) && (service === "all" || incident.service === service);
  });

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="MONITOR / INCIDENT INTAKE"
        title="Incidents"
        description="Review and filter incident records received by the NEXORA control plane. Filters run against the loaded API response."
        actions={<button className="secondary-button" type="button" onClick={load} disabled={loading}><Icon name="refresh" size={14} /> {loading ? "Refreshing…" : "Refresh feed"}</button>}
      />
      <Panel>
        <SectionHeading eyebrow="LIVE API FEED" title="Incident register" description={`${incidents.length} records returned from the Phase 1 incident endpoint.`} action={<StatusBadge value="api-backed" label="API-backed" dot />} />
        <div className="filter-bar" aria-label="Incident filters">
          <label className="filter-search"><Icon name="search" size={15} /><span className="sr-only">Search incidents</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, service, description" /></label>
          <label><span className="sr-only">Filter by severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value as Severity | "all")}><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
          <label><span className="sr-only">Filter by status</span><select value={status} onChange={(event) => setStatus(event.target.value as IncidentStatus | "all")}><option value="all">All statuses</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="requires_human">Requires human</option><option value="resolved">Resolved</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option></select></label>
          <label><span className="sr-only">Filter by service</span><select value={service} onChange={(event) => setService(event.target.value)}><option value="all">All services</option>{services.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        </div>
        {loading ? <LoadingState label="Loading incidents…" rows={4} /> : null}
        {error ? <ErrorState title="Incident feed unavailable" description={error} onRetry={load} /> : null}
        {!loading && !error && filtered.length === 0 ? <EmptyState title={incidents.length ? "No incidents match these filters" : "No incidents received"} description={incidents.length ? "Adjust the filters to view other loaded records." : "New records will appear here when they are submitted through the API."} /> : null}
        {!loading && !error && filtered.length > 0 ? <IncidentTable incidents={filtered} /> : null}
      </Panel>
    </section>
  );
}
