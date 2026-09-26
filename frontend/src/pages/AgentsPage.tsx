import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { Icon, type IconName } from "../components/Icon";

interface AgentDefinition {
  name: string;
  domain: string;
  icon: IconName;
}

const agents: AgentDefinition[] = [
  { name: "Orchestrator Agent", domain: "Coordinates bounded specialist work", icon: "command" },
  { name: "IT Operations Agent", domain: "Incidents, logs, metrics, deployments", icon: "operations" },
  { name: "Revenue Agent", domain: "Payments, billing, checkout", icon: "business" },
  { name: "Support Agent", domain: "Tickets, customer issues, knowledge", icon: "agents" },
  { name: "Supply Chain Agent", domain: "Suppliers, inventory, shipments", icon: "layers" },
  { name: "Contract Agent", domain: "Obligations, renewals, penalties", icon: "reports" },
  { name: "Cloud Agent", domain: "Resources, usage, cost anomalies", icon: "database" },
  { name: "Data Agent", domain: "Pipelines, quality, anomalies", icon: "activity" },
  { name: "Compliance Agent", domain: "Controls, evidence, gaps", icon: "shield" }
];

export function AgentsPage() {
  return (
    <section className="page-section">
      <PageHeader eyebrow="INTELLIGENCE / AGENT FABRIC" title="Agent directory" description="The future specialist-agent topology is visible here, while every runtime status remains honest about what Phase 2 has configured." meta={<><Icon name="shield" size={13} /> No autonomous agents are running</>} />
      <Panel>
        <SectionHeading eyebrow="AGENT ARCHITECTURE" title="Specialist agent boundary" description="These are registered product roles, not fabricated active sessions." action={<StatusBadge value="phase-4" label="Phase 4 boundary" />} />
        <div className="agent-grid">
          {agents.map((agent) => (
            <article className="agent-card" key={agent.name}>
              <div className="agent-card-top"><span className="agent-icon"><Icon name={agent.icon} size={18} /></span><StatusBadge value="not-configured" label="Not configured" /></div>
              <h3>{agent.name}</h3>
              <p>{agent.domain}</p>
              <div className="agent-meta"><span>Current task</span><strong>Not available</strong></div>
              <div className="agent-meta"><span>Last activity</span><strong>Not recorded</strong></div>
            </article>
          ))}
        </div>
      </Panel>
      <div className="source-note"><Icon name="layers" size={15} /> Agent contracts and the state machine are available in the backend foundation. Runtime orchestration is intentionally deferred.</div>
    </section>
  );
}
