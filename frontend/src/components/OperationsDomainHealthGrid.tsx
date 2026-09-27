import { Link } from "react-router-dom";

import { formatDateTime, humanize } from "../lib/format";
import type { DomainHealth } from "../types";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

const labels: Record<DomainHealth["domain"], string> = {
  IT: "IT Operations",
  REVENUE: "Revenue",
  SUPPORT: "Customer Support",
  SUPPLY_CHAIN: "Supply Chain",
  CONTRACTS: "Contracts",
  CLOUD: "Cloud",
  DATA: "Data",
  COMPLIANCE: "Compliance"
};

export function OperationsDomainHealthGrid({ domains }: { domains: DomainHealth[] }) {
  return (
    <div className="operations-domain-grid">
      {domains.map((domain) => (
        <Link className="operations-domain-card" to={`/operations/${domain.domain.toLowerCase()}`} key={domain.domain}>
          <div className="operations-domain-card-top">
            <div>
              <span className="eyebrow">{domain.domain}</span>
              <h3>{labels[domain.domain]}</h3>
            </div>
            <StatusBadge value={domain.status} label={humanize(domain.status)} dot />
          </div>
          <div className="operations-health-line">
            <strong>{domain.health_score === null ? "—" : `${Math.round(domain.health_score)}%`}</strong>
            <span>health score</span>
          </div>
          <div className="operations-domain-meta">
            <span>{domain.active_signals.length} active signals</span>
            <span>{domain.business_impact.impact_level} impact</span>
          </div>
          <div className="operations-domain-source">
            <span className={domain.simulator ? "source-label source-simulator" : "source-label"}>
              {domain.simulator ? "SIMULATED / CONTROLLED DEMONSTRATION" : domain.source.label}
            </span>
            <span>{domain.last_updated ? formatDateTime(domain.last_updated) : "Not updated"}</span>
            <Icon name="arrow" size={13} />
          </div>
        </Link>
      ))}
    </div>
  );
}
