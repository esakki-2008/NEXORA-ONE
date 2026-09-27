import { humanize } from "../lib/format";
import type { BusinessImpact } from "../types";
import { StatusBadge } from "./StatusBadge";

export function OperationsImpactPanel({ impact }: { impact: BusinessImpact }) {
  const revenue = impact.estimated_revenue_impact === null
    ? "Not available"
    : `${impact.estimated_revenue_impact.toFixed(2)} ${impact.currency ?? "currency"}`;

  return (
    <div className="operations-impact-grid">
      <div className="operations-impact-primary">
        <span className="eyebrow">DETERMINISTIC IMPACT</span>
        <div className="operations-impact-heading">
          <strong>{humanize(impact.impact_level)}</strong>
          <StatusBadge value={impact.impact_level} label={humanize(impact.impact_level)} dot />
        </div>
        <p>{impact.operational_scope}</p>
        <span className="table-subtext">Impact is calculated from observed scope, severity, customer and transaction signals.</span>
      </div>
      <div className="operations-impact-stat"><span>Affected domains</span><strong>{impact.affected_domains.length || "—"}</strong></div>
      <div className="operations-impact-stat"><span>Customer estimate</span><strong>{impact.estimated_customer_impact ?? "—"}</strong><small>{impact.simulator ? "simulator estimate" : "source estimate"}</small></div>
      <div className="operations-impact-stat"><span>Revenue exposure</span><strong>{revenue}</strong><small>{impact.simulator ? "simulator estimate" : "source estimate"}</small></div>
    </div>
  );
}
