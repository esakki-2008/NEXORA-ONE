import type { IncidentStatus, Severity } from "../types";
import { humanize } from "../lib/format";

type BadgeValue = string | Severity | IncidentStatus;

interface StatusBadgeProps {
  value: BadgeValue;
  label?: string;
  dot?: boolean;
}

export function StatusBadge({ value, label, dot = false }: StatusBadgeProps) {
  const className = value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <span className={`status-badge status-${className}`}>
      {dot ? <span className="status-dot" aria-hidden="true" /> : null}
      {label ?? humanize(value)}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <StatusBadge value={severity} dot />;
}
