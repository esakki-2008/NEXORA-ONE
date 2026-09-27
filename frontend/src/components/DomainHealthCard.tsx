import { Link } from "react-router-dom";

import { domainDefinitions, incidentsForDomain } from "../lib/domains";
import type { Incident } from "../types";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

export function DomainHealthCard({ incidents }: { incidents: Incident[] }) {
  return (
    <div className="domain-grid">
      {domainDefinitions.map((domain) => {
        const domainIncidents = incidentsForDomain(incidents, domain);
        const isAttention = domainIncidents.some((incident) => !["resolved", "closed", "cancelled"].includes(incident.status));
        const status = !domain.configured ? "not-configured" : isAttention ? "attention" : "no-issues";
        const statusLabel = !domain.configured ? "Not configured" : isAttention ? "Attention" : "No active issues";
        const summary = !domain.configured
          ? "No connected source in Phase 2."
          : domainIncidents.length
            ? `${domainIncidents.length} incident record${domainIncidents.length === 1 ? "" : "s"} in live intake.`
            : "No active incident records in live intake.";

        return (
          <Link className="domain-card" to={domain.path} key={domain.key}>
            <div className="domain-card-top">
              <span className="domain-icon"><Icon name={domain.key === "compliance" ? "shield" : domain.key === "data" ? "database" : "business"} size={17} /></span>
              <StatusBadge value={status} label={statusLabel} dot />
            </div>
            <h3>{domain.label}</h3>
            <p>{summary}</p>
            <div className="domain-card-footer">
              <span>{domain.configured ? `${domainIncidents.length} records` : "Source pending"}</span>
              <Icon name="arrow" size={14} />
            </div>
          </Link>
        );
      })}
    </div>
  );
}
