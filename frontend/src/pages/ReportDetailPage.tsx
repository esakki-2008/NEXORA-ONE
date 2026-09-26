import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import { getIncident, getIncidentReport } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, formatUnknown, humanize } from "../lib/format";
import type { Incident, IncidentReport } from "../types";

export function ReportDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const loader = useCallback(async (): Promise<{ incident: Incident; report: IncidentReport }> => {
    if (!incidentId) throw new Error("No incident id was supplied.");
    const [incident, report] = await Promise.all([getIncident(incidentId), getIncidentReport(incidentId)]);
    return { incident, report };
  }, [incidentId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [incidentId]);
  if (isLoading && !data) return <LoadingState label="Loading report…" rows={5} />;
  if (error && !data) return <ErrorState title="Report unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const { incident, report } = data;
  return (
    <section className="page-section">
      <Link className="back-link" to="/reports"><Icon name="arrow" size={14} /> Back to reports</Link>
      <PageHeader eyebrow={`REPORT / ${report.id.slice(0, 8)}`} title={incident.title} description={report.summary} meta={<><Icon name="clock" size={13} /> Created {formatDateTime(report.created_at)}</>} actions={<div className="detail-badges"><SeverityBadge severity={incident.severity} /><StatusBadge value={report.final_status} label={humanize(report.final_status)} /></div>} />
      <div className="report-grid"><Panel><SectionHeading eyebrow="ROOT CAUSE" title="Root cause" /><p className="report-copy">{report.root_cause}</p></Panel><Panel><SectionHeading eyebrow="IMPACT" title="Business impact" /><p className="report-copy">{report.impact}</p></Panel></div>
      <div className="report-grid"><Panel><SectionHeading eyebrow="TIMELINE" title="Recorded timeline" />{report.timeline.length ? <div className="report-list">{report.timeline.map((item, index) => <div className="report-list-row" key={index}><span>{formatUnknown(item["timestamp"] ?? item["time"] ?? `Event ${index + 1}`)}</span><strong>{formatUnknown(item["message"] ?? item["event"] ?? item)}</strong></div>)}</div> : <EmptyState compact title="No timeline entries" description="The report contains no timeline entries." />}</Panel><Panel><SectionHeading eyebrow="VERIFICATION" title="Verification record" />{report.verification.length ? <div className="report-list">{report.verification.map((item, index) => <div className="report-list-row" key={index}><span>Check {index + 1}</span><strong>{formatUnknown(item)}</strong></div>)}</div> : <EmptyState compact title="No verification entries" description="The report contains no verification entries." />}</Panel></div>
    </section>
  );
}
