import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { createAction, getActionRegistry, listActions } from "../api/actions";
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
import { humanize } from "../lib/format";
import type {
  ActionRegistryDefinition,
  ControlledAction,
  Incident,
  RiskLevel
} from "../types";

interface ActionsData {
  actions: ControlledAction[];
  registry: ActionRegistryDefinition[];
  incidents: Incident[];
}

interface ParameterField {
  name: string;
  label: string;
  type: "text" | "number" | "select";
  options?: string[];
  placeholder?: string;
}

const actionFields: Record<string, ParameterField[]> = {
  rollback_simulated_deployment: [
    { name: "deployment_id", label: "Deployment identifier", type: "text", placeholder: "Known simulated deployment id" }
  ],
  clear_simulated_queue: [
    { name: "queue_name", label: "Queue", type: "select", options: ["payment", "checkout", "order-processing", "fulfillment"] }
  ],
  disable_simulated_feature_flag: [
    { name: "feature_name", label: "Feature flag", type: "select", options: ["new_checkout", "payment_retries", "express_checkout", "fraud_screening"] }
  ],
  restore_simulated_configuration: [
    { name: "configuration_id", label: "Known-good configuration", type: "select", options: ["gateway.retry_limit", "gateway.endpoint", "checkout.timeout_ms", "connection.pool_size"] }
  ],
  scale_simulated_service: [
    { name: "service_name", label: "Service", type: "select", options: ["Payment Service", "Checkout Service", "Inventory", "Support System"] },
    { name: "desired_capacity", label: "Desired capacity", type: "number", placeholder: "1–100" }
  ]
};

const defaultParameterValues: Record<string, Record<string, string | number>> = {
  clear_simulated_queue: { queue_name: "payment" },
  disable_simulated_feature_flag: { feature_name: "payment_retries" },
  restore_simulated_configuration: { configuration_id: "gateway.retry_limit" },
  scale_simulated_service: { service_name: "Payment Service", desired_capacity: 4 }
};

function riskCopy(risk: RiskLevel): string {
  if (risk === "HIGH") return "Stronger human approval; never auto-execute.";
  if (risk === "MEDIUM") return "Explicit human approval required.";
  if (risk === "LOW") return "Policy-controlled low-risk change.";
  return "Read-only policy boundary.";
}

function buildParameters(actionName: string, values: Record<string, string | number>): Record<string, unknown> {
  const fields = actionFields[actionName] ?? [];
  return Object.fromEntries(
    fields
      .map((field) => [field.name, field.type === "number" ? Number(values[field.name]) : values[field.name]])
      .filter(([, value]) => value !== undefined && value !== "" && !Number.isNaN(value))
  );
}

export function ActionsPage() {
  const [searchParams] = useSearchParams();
  const [selectedIncident, setSelectedIncident] = useState(searchParams.get("incidentId") ?? "");
  const [selectedScenario, setSelectedScenario] = useState(searchParams.get("scenarioId") ?? "payment-failure");
  const [selectedAction, setSelectedAction] = useState("restart_payment_service");
  const [parameterValues, setParameterValues] = useState<Record<string, string | number>>({});
  const [actor, setActor] = useState("phase7-planner");
  const [submitting, setSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const loader = useCallback(async (): Promise<ActionsData> => {
    const [actions, registry, incidents] = await Promise.all([
      listActions(),
      getActionRegistry(),
      listIncidents()
    ]);
    return { actions, registry, incidents };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  useEffect(() => {
    if (!selectedIncident && data?.incidents.length) setSelectedIncident(data.incidents[0].id);
  }, [data?.incidents, selectedIncident]);

  useEffect(() => {
    setParameterValues(defaultParameterValues[selectedAction] ?? {});
  }, [selectedAction]);

  const selectedDefinition = data?.registry.find((definition) => definition.name === selectedAction) ?? null;
  const actions = useMemo(
    () => [...(data?.actions ?? [])].sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()),
    [data?.actions]
  );
  const pending = actions.filter((action) => ["PENDING_APPROVAL", "PROPOSED"].includes(action.status));
  const inFlight = actions.filter((action) => ["EXECUTING", "REQUIRES_HUMAN"].includes(action.status));
  const completed = actions.filter((action) => ["COMPLETED", "ROLLED_BACK"].includes(action.status));
  const highRisk = actions.filter((action) => action.risk_level === "HIGH" && !["COMPLETED", "ROLLED_BACK", "CANCELLED"].includes(action.status));

  const submitProposal = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedIncident) {
      setSubmitMessage("Select an incident before creating a controlled proposal.");
      return;
    }
    setSubmitting(true);
    setSubmitMessage(null);
    try {
      const action = await createAction({
        incident_id: selectedIncident,
        scenario_id: selectedScenario || null,
        action_name: selectedAction,
        parameters: buildParameters(selectedAction, parameterValues),
        requested_by: actor.trim() || "Local operator",
        idempotency_key: `ui-${selectedIncident}-${selectedAction}-${Date.now()}`
      });
      setSubmitMessage(`Proposal ${action.action_id.slice(0, 8)} created. Review the exact fingerprint before approval.`);
      reload();
    } catch (requestError) {
      setSubmitMessage(requestError instanceof Error ? requestError.message : "The server rejected this proposal safely.");
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading && !data) return <LoadingState label="Loading controlled action registry…" rows={7} />;
  if (error && !data) return <ErrorState title="Controlled actions unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="ACTION / PHASE 7 CONTROLLED AUTONOMY"
        title="Controlled Actions"
        description="A human-gated action plane for deterministic ShopFlow simulator changes. AI may inform a proposal; only this allow-listed registry can execute it."
        meta={<><Icon name="shield" size={13} /> SIMULATED / CONTROLLED DEMONSTRATION <span className="meta-separator">·</span> Server-calculated risk and immutable fingerprints</>}
        actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> {isLoading ? "Refreshing…" : "Refresh actions"}</button>}
      />

      <div className="controlled-action-banner">
        <div className="controlled-action-banner-mark"><Icon name="shield" size={18} /></div>
        <div><strong>No production control is implied.</strong><span>Every execution is bounded to deterministic in-memory ShopFlow state, recorded in an append-only audit chain, and verified before an incident can be resolved.</span></div>
        <StatusBadge value="simulated" label="SIMULATED" dot />
      </div>

      <div className="metric-grid metric-grid-command action-metric-grid">
        <div className="metric-card metric-tone-warning"><span className="eyebrow">AWAITING APPROVAL</span><strong>{pending.length}</strong><span className="muted">Human decision required</span></div>
        <div className="metric-card metric-tone-info"><span className="eyebrow">CONTROLLED QUEUE</span><strong>{inFlight.length}</strong><span className="muted">Executing or escalated</span></div>
        <div className="metric-card metric-tone-critical"><span className="eyebrow">HIGH-RISK OPEN</span><strong>{highRisk.length}</strong><span className="muted">Never auto-executed</span></div>
        <div className="metric-card metric-tone-success"><span className="eyebrow">VERIFIED HISTORY</span><strong>{completed.length}</strong><span className="muted">Completed or rolled back</span></div>
      </div>

      <div className="action-workspace-grid">
        <Panel className="action-proposal-panel">
          <SectionHeading eyebrow="PROPOSAL INTAKE" title="Plan a registered action" description="Parameters are normalized and validated on the server. Risk, rollback metadata, and the fingerprint are never accepted from this form." />
          <form className="action-form" onSubmit={submitProposal}>
            <label><span>Incident binding</span><select value={selectedIncident} onChange={(event) => setSelectedIncident(event.target.value)} required><option value="">Select an incident</option>{data.incidents.map((incident) => <option value={incident.id} key={incident.id}>{incident.title} · {incident.id.slice(0, 8)}</option>)}</select></label>
            <div className="form-two-column"><label><span>ShopFlow scenario</span><select value={selectedScenario} onChange={(event) => setSelectedScenario(event.target.value)}><option value="payment-failure">Payment failure</option><option value="database-failure">Database failure</option><option value="latency-spike">Latency spike</option><option value="bad-deployment">Bad deployment</option><option value="configuration-mismatch">Configuration mismatch</option></select></label><label><span>Requested by</span><input value={actor} onChange={(event) => setActor(event.target.value)} maxLength={200} /></label></div>
            <label><span>Allow-listed action</span><select value={selectedAction} onChange={(event) => setSelectedAction(event.target.value)}>{data.registry.map((definition) => <option value={definition.name} key={definition.name}>{humanize(definition.name)} · {definition.risk_level}</option>)}</select></label>
            {selectedDefinition ? <div className="action-definition-callout"><div><StatusBadge value={selectedDefinition.risk_level} label={`${selectedDefinition.risk_level} risk`} dot /><strong>{riskCopy(selectedDefinition.risk_level)}</strong></div><p>{selectedDefinition.description}</p><span>{selectedDefinition.expected_impact}</span></div> : null}
            {(actionFields[selectedAction] ?? []).map((field) => <label key={field.name}><span>{field.label}</span>{field.type === "select" ? <select value={String(parameterValues[field.name] ?? field.options?.[0] ?? "")} onChange={(event) => setParameterValues((values) => ({ ...values, [field.name]: event.target.value }))}>{field.options?.map((option) => <option value={option} key={option}>{option}</option>)}</select> : <input type={field.type} min={field.type === "number" ? 1 : undefined} max={field.type === "number" ? 100 : undefined} placeholder={field.placeholder} value={parameterValues[field.name] ?? ""} onChange={(event) => setParameterValues((values) => ({ ...values, [field.name]: field.type === "number" ? Number(event.target.value) : event.target.value }))} required />}</label>)}
            <div className="action-form-footer"><span className="muted">Create only. Approval and execution are separate explicit controls.</span><button className="primary-button" type="submit" disabled={submitting || !selectedIncident}><Icon name="plus" size={14} /> {submitting ? "Planning…" : "Create proposal"}</button></div>
            {submitMessage ? <div className="inline-alert action-form-message"><Icon name="shield" size={15} /> {submitMessage}</div> : null}
          </form>
        </Panel>

        <Panel>
          <SectionHeading eyebrow="REGISTRY BOUNDARY" title="Seven allowed actions" description="No arbitrary command, tool name, shell, or production endpoint is available through this surface." />
          <div className="registry-list">{data.registry.map((definition) => <div className="registry-row" key={definition.name}><div className="registry-row-main"><span className="registry-glyph"><Icon name="arrow" size={12} /></span><div><strong>{humanize(definition.name)}</strong><span>{definition.name}</span></div></div><StatusBadge value={definition.risk_level} label={definition.risk_level} dot /></div>)}</div>
        </Panel>
      </div>

      <Panel>
        <SectionHeading eyebrow="APPROVAL QUEUE" title="Human review required" description="Open an action to inspect its incident binding, normalized parameters, risk, rollback plan, and immutable fingerprint before approving." action={<StatusBadge value={pending.length ? "pending" : "clear"} label={`${pending.length} pending`} dot />} />
        {pending.length ? <div className="approval-queue">{pending.map((action) => <Link className="approval-queue-row" to={`/remediation/${action.action_id}`} key={action.action_id}><div><StatusBadge value={action.risk_level} label={action.risk_level} dot /><strong>{humanize(action.action_name)}</strong><span>{action.incident_id.slice(0, 8)} · {action.scenario_id ?? "no scenario"}</span></div><div><span className="approval-queue-impact">{action.expected_impact}</span><span className="text-link">Review action <Icon name="arrow" size={13} /></span></div></Link>)}</div> : <EmptyState compact title="Approval queue is clear" description="No action can execute without a fresh human decision bound to its fingerprint." />}
      </Panel>

      <Panel>
        <SectionHeading eyebrow="ACTION LEDGER" title="Controlled action history" description="Status reflects the server lifecycle, not optimistic frontend state." />
        {actions.length ? <div className="table-wrap"><table className="data-table action-table"><thead><tr><th>Action</th><th>Risk</th><th>Status</th><th>Verification</th><th>Updated</th><th /></tr></thead><tbody>{actions.map((action) => <tr key={action.action_id}><td><Link className="incident-link" to={`/remediation/${action.action_id}`}><strong>{humanize(action.action_name)}</strong><span>{action.action_id.slice(0, 8)} · {action.incident_id.slice(0, 8)}</span></Link></td><td><StatusBadge value={action.risk_level} label={action.risk_level} dot /></td><td><StatusBadge value={action.status} dot /></td><td><StatusBadge value={action.verification_status} label={humanize(action.verification_status)} /></td><td><span className="table-subtext">{new Date(action.updated_at).toLocaleString()}</span></td><td><Link className="table-action" to={`/remediation/${action.action_id}`}>Open <Icon name="arrow" size={12} /></Link></td></tr>)}</tbody></table></div> : <EmptyState compact title="No controlled actions yet" description="Create a proposal from an incident to begin the observable plan, approval, execution, verification, and report flow." />}
      </Panel>
    </section>
  );
}
