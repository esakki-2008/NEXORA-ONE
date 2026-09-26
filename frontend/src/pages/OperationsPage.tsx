import { useCallback } from "react";

import { listIncidents } from "../api/incidents";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { domainDefinitions, incidentsForDomain } from "../lib/domains";
import type { Incident } from "../types";

export function OperationsPage() {
  const loader = useCallback(() => listIncidents(), []);
  const { data, isLoading, error, reload } = useAsyncData<Incident[]>(loader);

  if (isLoading && !data) return <LoadingState label="Loading operations sources…" rows={6} />;
  if (error && !data) return <ErrorState title="Operations view is unavailable" description={error} onRetry={reload} />;

  const incidents = data ?? [];

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="MONITOR / OPERATIONS"
        title="Unified operations"
        description="Cross-domain operational posture without splitting the business into separate applications."
        actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh operations</button>}
      />
      <Panel>
        <SectionHeading eyebrow="DOMAIN REGISTER" title="Operational domains" description="Issue counts are derived from the live incident API. A dash means the domain is not connected, not zero." />
        <div className="operations-table-wrap">
          <table className="operations-table">
            <thead><tr><th>Domain</th><th>Status</th><th>Active issues</th><th>Source boundary</th><th>Next surface</th></tr></thead>
            <tbody>
              {domainDefinitions.map((domain) => {
                const domainIncidents = incidentsForDomain(incidents, domain);
                const active = domainIncidents.filter((incident) => !["resolved", "closed", "cancelled"].includes(incident.status));
                const configured = domain.configured;
                return (
                  <tr key={domain.key}>
                    <td><strong>{domain.label}</strong><span className="table-subtext">{domain.description}</span></td>
                    <td><StatusBadge value={!configured ? "not-configured" : active.length ? "attention" : "no-issues"} label={!configured ? "Not configured" : active.length ? "Attention" : "No active issues"} dot /></td>
                    <td className="table-number">{configured ? active.length : "—"}</td>
                    <td><span className="muted">{configured ? "Incident API / ShopFlow" : "No connected source"}</span></td>
                    <td><span className="table-action"><Icon name="arrow" size={14} /> {domain.key === "it" ? "Incidents" : "Monitor"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="operations-footnote"><Icon name="layers" size={15} /> Controlled actions are not enabled in Phase 2. This view is observational only.</div>
    </section>
  );
}
