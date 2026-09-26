import type { IncidentStatus, Severity } from "../types";

type BadgeValue = Severity | IncidentStatus | "online" | "offline" | "loading";

function labelFor(value: string): string {
  return value.replace(/_/g, " ");
}

export function StatusBadge({ value }: { value: BadgeValue }) {
  return <span className={`status-badge status-${value}`}>{labelFor(value)}</span>;
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <StatusBadge value={severity} />;
}
