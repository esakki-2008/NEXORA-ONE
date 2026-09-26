import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  detail: string;
  tone?: "default" | "critical" | "success" | "warning" | "info";
  icon?: ReactNode;
}

export function MetricCard({ label, value, detail, tone = "default", icon }: MetricCardProps) {
  return (
    <div className={`metric-card metric-tone-${tone}`}>
      <div className="metric-card-top"><span className="eyebrow">{label}</span>{icon ? <span className="metric-icon">{icon}</span> : null}</div>
      <strong>{value}</strong>
      <span className="muted">{detail}</span>
    </div>
  );
}
