import { useCallback } from "react";
import { Link } from "react-router-dom";

import { listActions, listVerifications } from "../api/orchestrator";
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
import type { ActionRecord, VerificationRecord } from "../types";

interface VerificationData {
  verifications: VerificationRecord[];
  actions: ActionRecord[];
}

export function VerificationPage() {
  const loader = useCallback(async (): Promise<VerificationData> => {
    const [verifications, actions] = await Promise.all([listVerifications(), listActions()]);
    return { verifications, actions };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  if (isLoading && !data) return <LoadingState label="Loading verification records…" rows={5} />;
  if (error && !data) return <ErrorState title="Verification center unavailable" description={error} onRetry={reload} />;

  const verifications = data?.verifications ?? [];
  const actions = data?.actions ?? [];

  return (
    <section className="page-section">
      <PageHeader eyebrow="ACTION / VERIFICATION" title="Verification center" description="Post-action proof returned by the server-side orchestrator. Resolution is never inferred from an action alone." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh records</button>} />
      <Panel>
        <SectionHeading eyebrow="POST-ACTION PROOF" title="Verification register" description="Every row below is a recorded check with expected and actual structured results." action={<StatusBadge value={verifications.length ? "recorded" : "not-recorded"} label={verifications.length ? `${verifications.length} checks` : "No checks recorded"} />} />
        {verifications.length ? <div className="verification-list">{verifications.map((record) => <div className="verification-row" key={record.id}><div className="verification-title"><span className="verification-icon"><Icon name="verification" size={16} /></span><div><Link to={`/incidents/${record.incident_id}`}><strong>{humanize(record.check)}</strong></Link><span>{record.incident_id.slice(0, 8)} · {formatDateTime(record.timestamp)}</span></div></div><div className="verification-checks"><span>Expected <b>{record.expected_result.passed === true ? "PASS" : "Recorded"}</b></span><span>Actual <b>{record.status === "VERIFIED" ? "PASS" : humanize(record.status)}</b></span></div><StatusBadge value={record.status} label={humanize(record.status)} dot /></div>)}</div> : <EmptyState title="No verification records" description="A verification record will appear only after an approved controlled action has run its server-side checks." />}
      </Panel>
      <Panel>
        <SectionHeading eyebrow="CONTROLLED ACTIONS" title="Action execution register" description="Execution records include the approval status and simulator result returned by the backend." action={<StatusBadge value={actions.length ? "recorded" : "not-recorded"} label={actions.length ? `${actions.length} actions` : "No actions recorded"} />} />
        {actions.length ? <div className="verification-list">{actions.map((action) => <div className="verification-row" key={action.action_id}><div className="verification-title"><span className="verification-icon"><Icon name="remediation" size={16} /></span><div><Link to={`/incidents/${action.incident_id}`}><strong>{humanize(action.action)}</strong></Link><span>{action.incident_id.slice(0, 8)} · {formatDateTime(action.timestamp)}</span></div></div><div className="verification-checks"><span>Risk <b>{action.risk_level}</b></span><span>Approval <b>{action.approval_status ?? "—"}</b></span></div><StatusBadge value={action.status} label={humanize(action.status)} dot /></div>)}</div> : <EmptyState compact title="No controlled actions" description="No simulated action has been executed through the approval gate." />}
      </Panel>
      <div className="verification-legend"><StatusBadge value="server-owned" label="Server-owned" dot /><span>The frontend can request or display a decision; it cannot approve, execute, or mark an incident resolved by itself.</span></div>
    </section>
  );
}
