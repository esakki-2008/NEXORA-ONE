import { useCallback } from "react";
import { Link } from "react-router-dom";

import { listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { Incident } from "../types";

export function VerificationPage() {
  const loader = useCallback(() => listIncidents(), []);
  const { data, isLoading, error, reload } = useAsyncData<Incident[]>(loader);
  if (isLoading && !data) return <LoadingState label="Loading verification records…" rows={5} />;
  if (error && !data) return <ErrorState title="Verification center unavailable" description={error} onRetry={reload} />;
  const incidents = data ?? [];

  return (
    <section className="page-section">
      <PageHeader eyebrow="ACTION / VERIFICATION" title="Verification center" description="A visual foundation for proving that controlled actions changed the expected state. No verification runner is active in Phase 2." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh records</button>} />
      <Panel>
        <SectionHeading eyebrow="POST-ACTION PROOF" title="Verification register" description="The API currently records incidents only; before and after checks will populate after the verification phase." action={<StatusBadge value="not-enabled" label="Not enabled" />} />
        {incidents.length ? <div className="verification-list">{incidents.map((incident) => <div className="verification-row" key={incident.id}><div className="verification-title"><span className="verification-icon"><Icon name="verification" size={16} /></span><div><Link to={`/incidents/${incident.id}`}><strong>{incident.title}</strong></Link><span>{incident.service} · received {formatDateTime(incident.created_at)}</span></div></div><div className="verification-checks"><span>Before <b>—</b></span><span>After <b>—</b></span><span>Tests <b>—</b></span></div><StatusBadge value="pending" label={humanize("pending")} /></div>)}</div> : <EmptyState title="No incidents require verification" description="Verification records will appear after an approved action has a registered check." />}
      </Panel>
      <div className="verification-legend"><StatusBadge value="pending" label="Pending" dot /><span>No remediation or verification logic is executed by this screen.</span></div>
    </section>
  );
}
