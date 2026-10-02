import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  approveAction,
  cancelAction,
  executeAction,
  getAction,
  getActionAudit,
  getActionVerification,
  rejectAction,
  rollbackAction
} from "../api/actions";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type {
  ActionAuditEvent,
  ActionDecisionRequest,
  ControlledAction,
  ControlledActionVerification
} from "../types";

interface ActionDetailData {
  action: ControlledAction;
  audit: ActionAuditEvent[];
  verification: ControlledActionVerification;
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function ActionDetailPage() {
  const { actionId } = useParams<{ actionId: string }>();
  const [actor, setActor] = useState("Local operator");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loader = useCallback(async (): Promise<ActionDetailData> => {
    if (!actionId) throw new Error("No action id was supplied.");
    const [action, audit, verification] = await Promise.all([
      getAction(actionId),
      getActionAudit(actionId),
      getActionVerification(actionId)
    ]);
    return { action, audit, verification };
  }, [actionId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [actionId]);

  const mutate = async (
    operation: (request: ActionDecisionRequest) => Promise<ControlledAction>,
    successMessage: string
  ) => {
    if (!actionId) return;
    setBusy(true);
    setMessage(null);
    try {
      await operation({ requested_by: actor.trim() || "Local operator", reason: reason.trim() || null });
      setMessage(successMessage);
      reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "The server rejected this control request safely.");
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!actionId) return;
    setBusy(true);
    setMessage(null);
    try {
      await rejectAction(actionId, { requested_by: actor.trim() || "Local operator", reason: reason.trim() || "Rejected during human review" });
      setMessage("Action rejected and retained in the audit history.");
      reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "The server rejected this control request safely.");
    } finally {
      setBusy(false);
    }
  };

  if (isLoading && !data) return <LoadingState label="Loading action fingerprint and audit chain…" rows={8} />;
  if (error && !data) return <ErrorState title="Controlled action unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const { action, audit, verification } = data;
  const canApprove = action.status === "PENDING_APPROVAL" || action.status === "PROPOSED";
  const canExecute = action.status === "APPROVED";
  const canCancel = ["PROPOSED", "PENDING_APPROVAL"].includes(action.status);
  const canRollback = ["COMPLETED", "FAILED", "REQUIRES_HUMAN"].includes(action.status) && action.rollback_supported;

  return (
    <section className="page-section">
      <Link className="back-link" to="/remediation"><Icon name="arrow" size={14} /> Back to controlled actions</Link>
      <PageHeader
        eyebrow={`ACTION DETAIL · ${action.action_id.slice(0, 8)}`}
        title={humanize(action.action_name)}
        description={action.expected_impact}
        meta={<><Icon name="clock" size={13} /> Updated {formatDateTime(action.updated_at)} <span className="meta-separator">·</span> {action.scenario_id ? "ShopFlow simulator bound" : "Scenario binding unavailable"}</>}
        actions={<div className="detail-badges"><StatusBadge value={action.risk_level} label={`${action.risk_level} risk`} dot /><StatusBadge value={action.status} dot /></div>}
      />

      <div className="controlled-action-banner action-detail-banner">
        <div className="controlled-action-banner-mark"><Icon name="shield" size={18} /></div>
        <div><strong>Approval is bound to this exact fingerprint.</strong><span>Any change to the incident, action name, normalized parameters, risk, or simulator binding invalidates the approval rather than widening authority.</span></div>
        <code>{action.action_fingerprint.slice(0, 16)}…</code>
      </div>

      <div className="metric-grid metric-grid-command action-metric-grid">
        <div className="metric-card"><span className="eyebrow">LIFECYCLE</span><strong className="metric-text">{humanize(action.status)}</strong><span className="muted">Server-owned state</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">VERIFICATION</span><strong className="metric-text">{humanize(action.verification_status)}</strong><span className="muted">{action.execution_attempts} execution attempt{action.execution_attempts === 1 ? "" : "s"}</span></div>
        <div className="metric-card"><span className="eyebrow">INCIDENT BINDING</span><strong className="metric-text">{action.incident_id.slice(0, 8)}</strong><span className="muted">Immutable relationship</span></div>
        <div className="metric-card metric-tone-warning"><span className="eyebrow">AUDIT REFERENCE</span><strong className="metric-text">{action.audit_reference}</strong><span className="muted">Hash-chained events</span></div>
      </div>

      <div className="detail-grid detail-grid-wide action-detail-grid">
        <Panel>
          <SectionHeading eyebrow="HUMAN CONTROL" title="Approval decision" description="Review the server-calculated risk and exact action details before making a decision." />
          <div className="action-review-list"><div><span>Risk</span><StatusBadge value={action.risk_level} label={action.risk_level} dot /></div><div><span>Requested by</span><strong>{action.requested_by}</strong></div><div><span>Approval state</span><strong>{action.approval_status ? humanize(action.approval_status) : "Not requested"}</strong></div><div><span>Rollback</span><strong>{action.rollback_supported ? "Supported · bounded simulator restore" : "Not supported"}</strong></div></div>
          <div className="action-decision-form"><label><span>Operator identity</span><input value={actor} onChange={(event) => setActor(event.target.value)} maxLength={200} /></label><label><span>Decision reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} maxLength={2000} placeholder="Record why this action is approved, rejected, executed, or rolled back." /></label><div className="decision-actions">{canApprove ? <button className="primary-button" type="button" disabled={busy} onClick={() => mutate((request) => approveAction(action.action_id, request), "Action approved. Execution remains a separate explicit control.")}><Icon name="check" size={14} /> Approve fingerprint</button> : null}{canApprove ? <button className="danger-button" type="button" disabled={busy} onClick={reject}><Icon name="close" size={14} /> Reject and escalate</button> : null}{canExecute ? <button className="primary-button" type="button" disabled={busy} onClick={() => mutate((request) => executeAction(action.action_id, request), "Execution completed or escalated; verification is recorded by the server.")}><Icon name="remediation" size={14} /> Execute controlled action</button> : null}{canCancel ? <button className="secondary-button" type="button" disabled={busy} onClick={() => mutate((request) => cancelAction(action.action_id, request), "Action cancelled before execution.")}><Icon name="close" size={14} /> Cancel</button> : null}{canRollback ? <button className="secondary-button" type="button" disabled={busy} onClick={() => mutate((request) => rollbackAction(action.action_id, request), "Rollback requested; review verification and incident state.")}><Icon name="history" size={14} /> Rollback and verify</button> : null}</div>{message ? <div className="inline-alert action-detail-message"><Icon name="shield" size={15} /> {message}</div> : null}</div>
        </Panel>
        <Panel>
          <SectionHeading eyebrow="PLAN CONTRACT" title="What will happen" description="This contract is generated by the server-side planner and registry, not by the browser." />
          <div className="action-plan-block"><div><span>Planning summary</span><p>{action.planning_summary}</p></div><div><span>Verification strategy</span><p>{action.verification_strategy}</p></div><div><span>Rollback plan</span><p>{action.rollback_plan}</p></div></div>
        </Panel>
      </div>

      <div className="detail-grid detail-grid-wide">
        <Panel><SectionHeading eyebrow="NORMALIZED PARAMETERS" title="Exact inputs" description="Only the registered schema is accepted; arbitrary parameters cannot reach the simulator." /><pre className="json-block">{prettyJson(action.normalized_parameters)}</pre><div className="fingerprint-block"><span>SHA-256 fingerprint</span><code>{action.action_fingerprint}</code><span>Idempotency key · {action.idempotency_key}</span></div></Panel>
        <Panel><SectionHeading eyebrow="VERIFICATION RECORD" title="Expected versus observed" description="The incident cannot be resolved unless the server proves the expected simulator state." action={<StatusBadge value={verification.status} label={humanize(verification.status)} dot />} /><div className="verification-record"><div><span>Details</span><p>{verification.details}</p></div><div className="verification-state-grid"><div><span>Before state</span><pre className="json-block compact-json">{prettyJson(verification.before_state)}</pre></div><div><span>After state</span><pre className="json-block compact-json">{prettyJson(verification.after_state)}</pre></div></div>{verification.rollback_status ? <div className="verification-rollback"><span>Rollback verification</span><StatusBadge value={verification.rollback_status} label={humanize(verification.rollback_status)} dot /></div> : null}</div></Panel>
      </div>

      <Panel>
        <SectionHeading eyebrow="APPEND-ONLY AUDIT" title="Control history" description="Each event is hash-chained. The browser only renders structured summaries and references." action={<StatusBadge value="immutable" label="Chain validated" dot />} />
        <div className="action-audit-list">{audit.map((event) => <div className="action-audit-row" key={event.event_id}><div className="audit-marker"><Icon name={event.event_type.includes("failed") || event.event_type === "action.human.escalation" ? "incidents" : "check"} size={13} /></div><div className="audit-copy"><div><strong>{humanize(event.event_type)}</strong><span>{formatDateTime(event.timestamp)}</span></div><p>{event.message}</p><code>{event.event_hash.slice(0, 18)}… · {event.actor}</code></div></div>)}</div>
      </Panel>
    </section>
  );
}
