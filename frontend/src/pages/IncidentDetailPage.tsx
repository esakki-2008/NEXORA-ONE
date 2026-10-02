import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import { getIncident, listIncidentActivity, listIncidentEvidence, listIncidentHypotheses } from "../api/incidents";
import { listPhase8Verifications } from "../api/verification";
import { ActivityTimeline } from "../components/ActivityTimeline";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { OrchestrationPanel } from "../components/OrchestrationPanel";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, formatDuration, humanize } from "../lib/format";
import type { ActivityEvent, Evidence, Hypothesis, Incident, Phase8VerificationRecord } from "../types";

interface IncidentDetailData {
  incident: Incident;
  activity: ActivityEvent[];
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  verifications: Phase8VerificationRecord[];
}

const stageSequence = [
  "INCIDENT_RECEIVED",
  "OBSERVING",
  "INVESTIGATING",
  "HYPOTHESIS_GENERATED",
  "VALIDATING",
  "REMEDIATION_PROPOSED",
  "WAITING_FOR_APPROVAL",
  "EXECUTING",
  "VERIFYING",
  "RESOLVED"
];

export function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const loader = useCallback(async (): Promise<IncidentDetailData> => {
    if (!incidentId) throw new Error("No incident id was supplied.");
    const [incident, activity, evidence, hypotheses, verifications] = await Promise.all([
      getIncident(incidentId),
      listIncidentActivity(incidentId),
      listIncidentEvidence(incidentId),
      listIncidentHypotheses(incidentId),
      listPhase8Verifications({ incidentId })
    ]);
    return { incident, activity, evidence, hypotheses, verifications };
  }, [incidentId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [incidentId]);

  if (isLoading && !data) return <LoadingState label="Loading incident record…" rows={5} />;
  if (error && !data) return <ErrorState title="Incident unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const { incident, activity, evidence, hypotheses, verifications } = data;
  const stageIndex = stageSequence.indexOf(incident.agent_state);

  return (
    <section className="page-section">
      <Link className="back-link" to="/incidents"><Icon name="arrow" size={14} /> Back to incidents</Link>
      <PageHeader
        eyebrow={`INCIDENT RECORD · ${incident.id.slice(0, 8)}`}
        title={incident.title}
        description={incident.description}
        meta={<><Icon name="clock" size={13} /> Received {formatDateTime(incident.created_at)}</>}
        actions={<div className="page-header-actions"><Link className="secondary-button" to={`/investigation/${incident.id}`}><Icon name="investigation" size={14} /> Open investigation</Link><Link className="primary-button" to={`/remediation?incidentId=${encodeURIComponent(incident.id)}&scenarioId=payment-failure`}><Icon name="remediation" size={14} /> Propose controlled action</Link></div>}
      />
      <div className="detail-badges detail-badges-page"><SeverityBadge severity={incident.severity} /><StatusBadge value={incident.status} dot /><StatusBadge value={incident.agent_state} label={humanize(incident.agent_state)} /></div>

      <OrchestrationPanel incidentId={incident.id} />

      <div className="metric-grid detail-metric-grid">
        <div className="metric-card"><span className="eyebrow">AFFECTED SERVICE</span><strong className="metric-text">{incident.service}</strong><span className="muted">From incident intake</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">CURRENT AI STAGE</span><strong className="metric-text">{humanize(incident.agent_state)}</strong><span className="muted">State recorded by backend</span></div>
        <div className="metric-card"><span className="eyebrow">EVIDENCE</span><strong>{evidence.length}</strong><span className="muted">Records attached</span></div>
        <div className="metric-card"><span className="eyebrow">DURATION</span><strong>{formatDuration(incident.created_at)}</strong><span className="muted">Derived from receive time</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">VERIFICATION PROOF</span><strong>{verifications.length}</strong><span className="muted">Execution is not resolution</span></div>
      </div>

      <div className="detail-grid detail-grid-wide">
        <Panel>
          <SectionHeading eyebrow="IMPACT" title="Operational context" description="Impact is shown only when it exists in the source record." />
          <div className="impact-block"><span className="impact-label">Description received</span><p>{incident.description}</p></div>
          <div className="detail-meta-list"><div><span>Service</span><strong>{incident.service}</strong></div><div><span>Severity</span><SeverityBadge severity={incident.severity} /></div><div><span>Last updated</span><strong>{formatDateTime(incident.updated_at)}</strong></div></div>
        </Panel>
        <Panel>
          <SectionHeading eyebrow="OBSERVABLE ACTIVITY" title="Incident timeline" description="Recorded API activity, not private model reasoning." />
          <ActivityTimeline events={activity} />
        </Panel>
      </div>

      <Panel className="stage-panel">
        <SectionHeading eyebrow="CONTROL STATE" title="Investigation lifecycle" description="The explicit backend state machine records each permitted transition; unresolved states remain visible until the server moves the incident safely." />
        <ol className="state-timeline">
          {stageSequence.map((stage, index) => {
            const isCurrent = index === stageIndex;
            const isRecordedBefore = index < stageIndex && stageIndex > 0;
            return <li className={`${isCurrent ? "state-current" : ""}${isRecordedBefore ? " state-recorded" : ""}`} key={stage}><span className="state-node">{isRecordedBefore ? <Icon name="check" size={12} /> : index + 1}</span><div><strong>{humanize(stage)}</strong><span>{isCurrent ? "Current backend state" : isRecordedBefore ? "Recorded before current state" : "Not started"}</span></div></li>;
          })}
        </ol>
      </Panel>

      <Panel>
        <SectionHeading eyebrow="PHASE 8 RESOLUTION GATE" title="Verification history" description="This incident is considered resolved only when a fresh server-owned proof passes every required check. Execution status alone never opens the gate." action={<Link className="text-link" to="/verification">Open verification center <Icon name="arrow" size={13} /></Link>} />
        {verifications.length ? <div className="verification-list">{verifications.map((record) => <div className="verification-row" key={record.verification_id}><div className="verification-title"><span className="verification-icon"><Icon name="verification" size={16} /></span><div><Link to={`/verification/${record.verification_id}`}><strong>{humanize(record.status)} · {humanize(record.strategy[0] ?? "Proof")}</strong></Link><span>{record.verification_id.slice(0, 12)} · Updated {formatDateTime(record.updated_at)}</span></div></div><div className="verification-checks"><span>Checks <b>{record.checks.length}</b></span><span>Confidence <b>{Math.round(record.confidence * 100)}%</b></span></div><StatusBadge value={record.status} label={humanize(record.status)} dot /></div>)}</div> : <EmptyState compact title="No Phase 8 proof" description="No verification record is attached to this incident. The resolution gate remains closed." />}
      </Panel>

      <div className="detail-grid detail-grid-wide">
        <Panel>
          <SectionHeading eyebrow="EVIDENCE LEDGER" title="Evidence collected" action={<Link className="text-link" to={`/investigation/${incident.id}`}>View investigation <Icon name="arrow" size={13} /></Link>} />
          {evidence.length ? <div className="mini-record-list">{evidence.slice(0, 5).map((item) => <div className="mini-record" key={item.id}><StatusBadge value={item.type} label={humanize(item.type)} /><div><strong>{item.summary}</strong><span>{item.source}</span></div></div>)}</div> : <EmptyState compact title="No evidence available" description="No evidence has been recorded for this incident." />}
        </Panel>
        <Panel>
          <SectionHeading eyebrow="HYPOTHESES" title="Structured reasoning summary" />
          {hypotheses.length ? <div className="mini-record-list">{hypotheses.map((item) => <div className="mini-record" key={item.id}><StatusBadge value={item.validation_status} label={humanize(item.validation_status)} /><div><strong>{item.title}</strong><span>{Math.round(item.confidence * 100)}% confidence</span></div></div>)}</div> : <EmptyState compact title="No hypotheses available" description="Hypothesis generation has not been recorded for this incident." />}
        </Panel>
      </div>
    </section>
  );
}
