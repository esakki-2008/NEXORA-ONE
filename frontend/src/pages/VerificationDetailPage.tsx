import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAction } from "../api/actions";
import {
  cancelVerification,
  getPhase8Verification,
  getVerificationEvidence,
  getVerificationTimeline,
  retryVerification,
  runVerification
} from "../api/verification";
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
  ControlledAction,
  Phase8VerificationEvidence,
  Phase8VerificationRecord,
  Phase8VerificationTimelineEvent
} from "../types";

interface VerificationDetailData {
  verification: Phase8VerificationRecord;
  evidence: Phase8VerificationEvidence[];
  timeline: Phase8VerificationTimelineEvent[];
  action: ControlledAction;
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function trustLabel(trust: string): string {
  return trust === "SIMULATED" ? "SIMULATED / CONTROLLED DEMONSTRATION" : humanize(trust);
}

export function VerificationDetailPage() {
  const { verificationId } = useParams<{ verificationId: string }>();
  const [actor, setActor] = useState("Local operator");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loader = useCallback(async (): Promise<VerificationDetailData> => {
    if (!verificationId) throw new Error("No verification id was supplied.");
    const verification = await getPhase8Verification(verificationId);
    const [evidence, timeline, action] = await Promise.all([
      getVerificationEvidence(verificationId),
      getVerificationTimeline(verificationId),
      getAction(verification.action_id)
    ]);
    return { verification, evidence, timeline, action };
  }, [verificationId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [verificationId]);

  const operate = async (operation: () => Promise<Phase8VerificationRecord>, success: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await operation();
      setMessage(success);
      reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "The server rejected this verification control safely.");
    } finally {
      setBusy(false);
    }
  };

  if (isLoading && !data) return <LoadingState label="Loading verification proof and evidence chain…" rows={8} />;
  if (error && !data) return <ErrorState title="Verification record unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const { verification, evidence, timeline, action } = data;
  const canRun = verification.status === "PENDING";
  const canRetry = ["FAILED", "INCONCLUSIVE", "RECOVERY_REQUIRED"].includes(verification.status) && verification.attempt < verification.max_attempts;
  const canCancel = ["PENDING", "FAILED", "INCONCLUSIVE", "RECOVERY_REQUIRED", "RETRYING"].includes(verification.status);

  return (
    <section className="page-section">
      <Link className="back-link" to="/verification"><Icon name="arrow" size={14} /> Back to verification center</Link>
      <PageHeader
        eyebrow={`VERIFICATION DETAIL · ${verification.verification_id.slice(0, 12)}`}
        title={`${humanize(verification.status)} proof`}
        description="A server-owned expected-versus-actual record. Passing this record is the only resolution proof accepted by the incident gate."
        meta={<><Icon name="clock" size={13} /> Updated {formatDateTime(verification.updated_at)} <span className="meta-separator">·</span> {trustLabel(evidence[0]?.trust ?? "UNAVAILABLE")}</>}
        actions={<div className="detail-badges"><StatusBadge value={verification.status} label={humanize(verification.status)} dot /><StatusBadge value={verification.attempt < verification.max_attempts ? "bounded" : "limit-reached"} label={`${verification.attempt}/${verification.max_attempts} attempts`} /></div>}
      />

      <div className="verification-control-banner">
        <div><strong>{humanize(action.action_name)}</strong><span>Incident <Link to={`/incidents/${action.incident_id}`}>{action.incident_id.slice(0, 12)}</Link> · Action <Link to={`/remediation/${action.action_id}`}>{action.action_id.slice(0, 12)}</Link></span></div>
        <div className="verification-control-actions"><label><span className="sr-only">Operator identity</span><input value={actor} onChange={(event) => setActor(event.target.value)} maxLength={200} /></label>{canRun ? <button className="primary-button" type="button" disabled={busy} onClick={() => operate(() => runVerification(verification.verification_id, actor.trim() || "Local operator"), "Verification attempt completed; reload to inspect the server result.")}><Icon name="verification" size={14} /> Run proof</button> : null}{canRetry ? <button className="primary-button" type="button" disabled={busy} onClick={() => operate(() => retryVerification(verification.verification_id, actor.trim() || "Local operator"), "Bounded retry completed; no automatic loop was started.")}><Icon name="refresh" size={14} /> Retry proof</button> : null}{canCancel ? <button className="secondary-button" type="button" disabled={busy} onClick={() => operate(() => cancelVerification(verification.verification_id, actor.trim() || "Local operator", "Cancelled from verification review"), "Verification cancelled; it cannot later prove resolution.")}><Icon name="close" size={14} /> Cancel</button> : null}</div>
      </div>
      {message ? <div className="inline-alert"><Icon name="shield" size={15} /> {message}</div> : null}

      <div className="metric-grid metric-grid-command verification-detail-metrics">
        <div className="metric-card"><span className="eyebrow">STATUS</span><strong className="metric-text">{humanize(verification.status)}</strong><span className="muted">Lifecycle state is server-owned</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">CONFIDENCE</span><strong className="metric-text">{Math.round(verification.confidence * 100)}%</strong><span className="muted">Deterministic factors only</span></div>
        <div className="metric-card"><span className="eyebrow">CHECKS</span><strong>{verification.checks.length}</strong><span className="muted">{verification.evidence_ids.length} evidence references</span></div>
        <div className="metric-card metric-tone-warning"><span className="eyebrow">ACTION EXECUTION</span><strong className="metric-text">{humanize(action.status)}</strong><span className="muted">Completion is not resolution</span></div>
      </div>

      {verification.failure_reason ? <div className="inline-alert"><Icon name="incidents" size={15} /> {verification.failure_reason}</div> : null}

      <div className="detail-grid detail-grid-wide">
        <Panel>
          <SectionHeading eyebrow="EXPECTED STATE" title="Server-owned target" description="Expected state was derived from the registered action and simulator boundary; the browser cannot submit or edit it." />
          <pre className="json-block">{prettyJson(verification.expected_state)}</pre>
        </Panel>
        <Panel>
          <SectionHeading eyebrow="ACTUAL STATE" title="Read-only observation" description="Actual state was collected through the allow-listed simulator/read-only boundary." />
          <pre className="json-block">{prettyJson(verification.actual_state)}</pre>
        </Panel>
      </div>

      <Panel>
        <SectionHeading eyebrow="CHECK LEDGER" title="Independent comparisons" description="Each check records status, expected value, actual value, comparison, timestamp, and evidence trust." />
        <div className="verification-check-ledger">
          {verification.checks.length ? verification.checks.map((check) => (
            <div className="verification-check-card" key={check.check_id}>
              <div className="verification-check-card-head"><div><strong>{humanize(check.name)}</strong><span>{check.strategy} · {check.comparison}</span></div><StatusBadge value={check.status} label={humanize(check.status)} dot /></div>
              <div className="verification-check-values"><div><span>Expected</span><pre>{prettyJson(check.expected_value)}</pre></div><div><span>Actual</span><pre>{prettyJson(check.actual_value)}</pre></div></div>
              <div className="verification-check-footer"><span>{check.observed_at ? formatDateTime(check.observed_at) : "No observation timestamp"}</span><StatusBadge value={check.trust} label={trustLabel(check.trust)} /><span>{check.evidence_ids.length} evidence link{check.evidence_ids.length === 1 ? "" : "s"}</span></div>
              {check.failure_reason ? <p className="verification-failure-text">{check.failure_reason}</p> : null}
            </div>
          )) : <div className="verification-empty-inline">No checks have run yet.</div>}
        </div>
      </Panel>

      <div className="detail-grid detail-grid-wide">
        <Panel>
          <SectionHeading eyebrow="CONFIDENCE FACTORS" title="Deterministic score inputs" description="No private chain-of-thought or arbitrary AI confidence is stored here." />
          <div className="factor-list">{Object.entries(verification.confidence_factors).map(([name, value]) => <div key={name}><span>{humanize(name)}</span><strong>{Math.round(value * 100)}%</strong><span className="factor-bar"><i style={{ width: `${Math.round(value * 100)}%` }} /></span></div>)}</div>
        </Panel>
        <Panel>
          <SectionHeading eyebrow="PROVENANCE EVIDENCE" title="Evidence references" description="Trust and simulator labeling remain visible rather than being promoted to production truth." />
          <div className="verification-evidence-list">{evidence.length ? evidence.map((item) => <div className="verification-evidence-row" key={item.evidence_id}><div><strong>{item.source}</strong><span>{item.evidence_id} · {formatDateTime(item.timestamp)}</span></div><div><StatusBadge value={item.trust} label={trustLabel(item.trust)} /><StatusBadge value={item.result} label={humanize(item.result)} /></div></div>) : <div className="verification-empty-inline">No evidence was recorded; the proof cannot open the resolution gate.</div>}</div>
        </Panel>
      </div>

      <Panel>
        <SectionHeading eyebrow="HASH-CHAINED TIMELINE" title="Verification activity" description="Append-only lifecycle events retain actor, transition context, and previous/event hashes." action={<StatusBadge value="immutable" label="Chain validated" dot />} />
        <div className="verification-timeline">{timeline.map((event) => <div className="verification-timeline-row" key={event.event_id}><span className="operations-event-marker" /><div><div><strong>{humanize(event.event_type)}</strong><span>{formatDateTime(event.timestamp)} · {event.actor}</span></div><p>{event.summary}</p><code>{event.event_hash.slice(0, 18)}… ← {event.previous_hash.slice(0, 12)}…</code></div></div>)}</div>
      </Panel>
    </section>
  );
}
