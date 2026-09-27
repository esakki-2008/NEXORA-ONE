import { useCallback, useState } from "react";

import { ApiError } from "../api/client";
import {
  approveOrchestration,
  getOrchestrationContext,
  rejectOrchestration,
  startOrchestration
} from "../api/orchestrator";
import { listScenarioSummaries } from "../api/simulator";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";
import { Panel } from "./Panel";
import { SectionHeading } from "./SectionHeading";
import { StatusBadge } from "./StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type {
  OrchestrationContext,
  OrchestrationActivity,
  ScenarioSummary
} from "../types";

interface OrchestrationPanelData {
  context: OrchestrationContext | null;
  scenarios: ScenarioSummary[];
}

interface OrchestrationPanelProps {
  incidentId: string;
  compact?: boolean;
}

function isContext(value: unknown): value is OrchestrationContext {
  return Boolean(
    value &&
      typeof value === "object" &&
      "current_state" in value &&
      "runtime_status" in value &&
      "incident_id" in value
  );
}

async function loadPanel(incidentId: string): Promise<OrchestrationPanelData> {
  let contextValue: OrchestrationContext | null = null;
  try {
    const response = await getOrchestrationContext(incidentId);
    contextValue = isContext(response) ? response : null;
  } catch (reason) {
    if (!(reason instanceof ApiError && reason.status === 404)) throw reason;
  }

  let scenarios: ScenarioSummary[] = [];
  try {
    const response = await listScenarioSummaries();
    scenarios = Array.isArray(response) ? response : [];
  } catch {
    // Scenario availability is optional; the live incident source remains explicit.
  }

  return { context: contextValue, scenarios };
}

function activityLabel(activity: OrchestrationActivity): string {
  return `${activity.message} · ${formatDateTime(activity.created_at)}`;
}

export function OrchestrationPanel({ incidentId, compact = false }: OrchestrationPanelProps) {
  const loader = useCallback(() => loadPanel(incidentId), [incidentId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [incidentId]);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [localContext, setLocalContext] = useState<OrchestrationContext | null>(null);

  const context = localContext ?? data?.context ?? null;
  const scenarios = data?.scenarios ?? [];

  async function runAction(action: () => Promise<OrchestrationContext>) {
    setActionBusy(true);
    setActionError(null);
    try {
      setLocalContext(await action());
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "The orchestration request failed.");
    } finally {
      setActionBusy(false);
    }
  }

  if (isLoading && !data) {
    return (
      <Panel>
        <SectionHeading eyebrow="CENTRAL ORCHESTRATOR" title="Loading control state" description="Reading server-side orchestration state…" />
      </Panel>
    );
  }

  if (error && !data) {
    return (
      <Panel>
        <SectionHeading eyebrow="CENTRAL ORCHESTRATOR" title="Control state unavailable" description="The UI will not infer orchestration activity while the server source is unavailable." />
        <div className="inline-alert inline-alert-danger"><Icon name="incidents" size={15} /> {error} <button className="text-link" type="button" onClick={reload}>Retry</button></div>
      </Panel>
    );
  }

  const pendingApproval = context?.approval?.status === "pending";
  const latestActivity = context?.activity?.slice(-4).reverse() ?? [];

  return (
    <Panel className={compact ? "orchestration-panel orchestration-panel-compact" : "orchestration-panel"}>
      <SectionHeading
        eyebrow="CENTRAL ORCHESTRATOR"
        title="Controlled response workflow"
        description="Server-owned state, evidence, policy, approval, execution, and verification. The UI cannot bypass the approval gate."
        action={context ? <StatusBadge value={context.current_state} label={humanize(context.current_state)} dot /> : <StatusBadge value="not-started" label="Not started" />}
      />
      {error && !data ? <div className="inline-alert"><Icon name="incidents" size={15} /> {error}</div> : null}
      {actionError ? <div className="inline-alert inline-alert-danger"><Icon name="incidents" size={15} /> {actionError}</div> : null}

      {!context ? (
        <div className="orchestration-start">
          <div>
            <strong>Orchestration has not started for this incident.</strong>
            <span>Start a server-side investigation. Choose a ShopFlow fixture only when you want a clearly labelled synthetic demonstration.</span>
          </div>
          <div className="orchestration-start-controls">
            <label>
              <span className="sr-only">Synthetic ShopFlow scenario</span>
              <select value={selectedScenario} onChange={(event) => setSelectedScenario(event.target.value)}>
                <option value="">Use live incident record</option>
                {scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.name} · synthetic demo</option>)}
              </select>
            </label>
            <button className="primary-button" type="button" disabled={actionBusy} onClick={() => void runAction(() => startOrchestration(incidentId, selectedScenario || undefined))}>
              <Icon name="investigation" size={14} /> {actionBusy ? "Starting…" : "Start controlled investigation"}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="orchestration-summary">
            <div><span>State</span><strong>{humanize(context.current_state)}</strong></div>
            <div><span>Runtime</span><strong>{humanize(context.runtime_status)}</strong></div>
            <div><span>Source</span><strong>{context.source_type === "synthetic_demo_data" ? "ShopFlow · synthetic demo" : "Live incident record"}</strong></div>
            <div><span>Specialist</span><strong>{context.selected_agent ? humanize(context.selected_agent) : "Not selected"}</strong></div>
          </div>
          {context.analysis_summary ? <div className="orchestration-summary-copy"><span className="eyebrow">INVESTIGATION SUMMARY</span><p>{context.analysis_summary}</p></div> : null}
          {context.errors.length ? <div className="inline-alert inline-alert-danger"><Icon name="incidents" size={15} /> {context.errors[context.errors.length - 1]}</div> : null}
          {pendingApproval && context.approval ? (
            <div className="approval-card">
              <div className="approval-card-heading"><div><span className="eyebrow">APPROVAL GATE</span><strong>{humanize(context.approval.requested_action)}</strong></div><StatusBadge value={context.approval.risk_level} label={`${context.approval.risk_level} risk`} dot /></div>
              <p>{context.approval.reason}</p>
              <div className="approval-meta"><span>Expected impact: {context.approval.expected_impact}</span><span>Expires {formatDateTime(context.approval.expires_at)}</span></div>
              <div className="approval-actions"><button className="primary-button" type="button" disabled={actionBusy} onClick={() => void runAction(() => approveOrchestration(context.approval!.approval_id, "Local operator", "Approved in NEXORA Command Center"))}><Icon name="check" size={14} /> {actionBusy ? "Executing…" : "Approve and execute"}</button><button className="secondary-button" type="button" disabled={actionBusy} onClick={() => void runAction(() => rejectOrchestration(context.approval!.approval_id, "Local operator", "Rejected in NEXORA Command Center"))}><Icon name="close" size={14} /> Reject and escalate</button></div>
            </div>
          ) : null}
          {context.remediation_plan ? <div className="orchestration-plan"><span className="eyebrow">REMEDIATION PLAN</span><strong>{context.remediation_plan.problem}</strong><div>{context.remediation_plan.steps.map((step) => <span key={step.id} className={step.is_change ? "plan-step plan-step-change" : "plan-step"}>{step.sequence}. {humanize(step.action)} · {step.risk_level}</span>)}</div></div> : null}
          {latestActivity.length ? <div className="orchestration-activity"><span className="eyebrow">AUDIT TRAIL</span>{latestActivity.map((activity) => <span key={activity.id}>{activityLabel(activity)}</span>)}</div> : <EmptyState compact title="No activity recorded" description="The server has not returned an auditable orchestration event yet." />}
        </>
      )}
      {!context && !scenarios.length ? <div className="source-note"><Icon name="layers" size={14} /> ShopFlow scenarios are unavailable; the live source option remains explicit.</div> : null}
      {context?.verification_outcome ? <div className="verification-legend"><StatusBadge value={context.verification_outcome} label={`Verification ${humanize(context.verification_outcome)}`} dot /><span>Resolution is recorded only after a successful server-side verification.</span></div> : null}
      <button className="text-link orchestration-refresh" type="button" onClick={reload} disabled={actionBusy}><Icon name="refresh" size={13} /> Refresh control state</button>
    </Panel>
  );
}
