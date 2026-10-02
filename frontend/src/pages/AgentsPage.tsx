import { useCallback } from "react";

import { listOrchestratorAgents } from "../api/orchestrator";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon, type IconName } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { OrchestratorSpecialist } from "../types";

const iconByAgent: Record<string, IconName> = {
  it_operations: "operations",
  revenue: "business",
  support: "agents",
  supply_chain: "layers",
  contracts: "reports",
  cloud: "database",
  data: "activity",
  compliance: "shield"
};

function iconFor(agent: OrchestratorSpecialist): IconName {
  return iconByAgent[agent.name] ?? "agents";
}

export function AgentsPage() {
  const loader = useCallback(() => listOrchestratorAgents(), []);
  const { data, isLoading, error, reload } = useAsyncData<OrchestratorSpecialist[]>(loader);

  if (isLoading && !data) return <LoadingState label="Loading specialist registry…" rows={5} />;
  if (error && !data) return <ErrorState title="Agent registry unavailable" description={error} onRetry={reload} />;

  const agents = data ?? [];

  return (
    <section className="page-section">
      <PageHeader eyebrow="INTELLIGENCE / AGENT FABRIC" title="Agent directory" description="Eight bounded specialist modules are registered behind the central orchestrator. Runtime status is shown only when returned by the backend." meta={<><Icon name="shield" size={13} /> Server-owned specialist registry</>} actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh agents</button>} />
      <Panel>
        <SectionHeading eyebrow="AGENT ARCHITECTURE" title="Specialist agent boundary" description="Specialists provide domain capabilities; the central orchestrator owns routing, policy, approvals, execution, and resolution." action={<StatusBadge value={agents.length ? "registered" : "not-available"} label={agents.length ? `${agents.length} registered` : "Not available"} />} />
        {agents.length ? <div className="agent-grid">{agents.map((agent) => <article className="agent-card" key={agent.name}><div className="agent-card-top"><span className="agent-icon"><Icon name={iconFor(agent)} size={18} /></span><StatusBadge value={agent.status} label={humanize(agent.status)} dot /></div><h3>{humanize(agent.name)}</h3><p>{humanize(agent.domain)} · {agent.capabilities.join(", ")}</p><div className="agent-meta"><span>Current task</span><strong>{agent.current_task ? humanize(agent.current_task) : "Not recorded"}</strong></div><div className="agent-meta"><span>Last activity</span><strong>{agent.last_activity ? formatDateTime(agent.last_activity) : "Not recorded"}</strong></div></article>)}</div> : <EmptyState title="No specialist runtime records" description="The backend did not return registered specialist modules. No agent status is inferred in the UI." />}
      </Panel>
      <div className="source-note"><Icon name="layers" size={15} /> The model can propose bounded work, but it cannot select permissions, approve actions, execute tools, or declare an incident resolved.</div>
    </section>
  );
}
