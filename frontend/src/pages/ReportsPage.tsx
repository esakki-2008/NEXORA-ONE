import { useCallback } from "react";
import { Link } from "react-router-dom";

import { getIncidentReport, listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { Incident, IncidentReport } from "../types";

interface ReportRow { incident: Incident; report: IncidentReport; }

async function loadReports(): Promise<ReportRow[]> {
  const incidents = await listIncidents();
  const rows = await Promise.all(incidents.map(async (incident) => {
    try {
      return { incident, report: await getIncidentReport(incident.id) };
    } catch {
      return null;
    }
  }));
  return rows.filter((row): row is ReportRow => row !== null);
}

export function ReportsPage() {
  const loader = useCallback(() => loadReports(), []);
  const { data, isLoading, error, reload } = useAsyncData(loader);
  if (isLoading && !data) return <LoadingState label="Loading incident reports…" rows={4} />;
  if (error && !data) return <ErrorState title="Reports unavailable" description={error} onRetry={reload} />;
  const reports = data ?? [];

  return (
    <section className="page-section">
      <PageHeader eyebrow="REPORTING / INCIDENT REPORTS" title="Reports" description="Generated incident reports are shown only when the backend has created a report record. No report is inferred from an open incident." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh reports</button>} />
      <Panel>
        <SectionHeading eyebrow="REPORT REGISTER" title={`${reports.length} generated reports`} description="Root cause, impact, remediation, and verification are read from report records." />
        {reports.length ? <div className="reports-table-wrap"><table className="data-table reports-table"><thead><tr><th>Incident</th><th>Severity</th><th>Root cause</th><th>Impact</th><th>Verification</th><th>Created</th></tr></thead><tbody>{reports.map(({ incident, report }) => <tr key={report.id}><td><Link className="incident-link" to={`/reports/${incident.id}`}><strong>{incident.title}</strong><span className="muted mono">{incident.id.slice(0, 8)}</span></Link></td><td><SeverityBadge severity={incident.severity} /></td><td className="evidence-summary">{report.root_cause}</td><td className="evidence-summary">{report.impact}</td><td><StatusBadge value={report.final_status} label={humanize(report.final_status)} /></td><td className="muted">{formatDateTime(report.created_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No generated reports" description="Reports will appear here after a real investigation and report-generation workflow has recorded one." />}
      </Panel>
    </section>
  );
}
