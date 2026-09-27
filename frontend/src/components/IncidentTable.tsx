import { Link } from "react-router-dom";

import { formatDuration, formatShortTime, humanize } from "../lib/format";
import type { Incident } from "../types";
import { SeverityBadge, StatusBadge } from "./StatusBadge";

interface IncidentTableProps {
  incidents: Incident[];
  compact?: boolean;
}

export function IncidentTable({ incidents, compact = false }: IncidentTableProps) {
  return (
    <div className="table-wrap">
      <table className="data-table incident-table">
        <thead>
          <tr>
            <th>Incident</th>
            <th>Service</th>
            <th>Severity</th>
            <th>Status</th>
            {!compact ? <th>AI stage</th> : null}
            <th>{compact ? "Received" : "Duration"}</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <tr key={incident.id}>
              <td>
                <Link className="incident-link" to={`/incidents/${incident.id}`}>
                  <strong>{incident.title}</strong>
                  <span className="muted mono">{incident.id.slice(0, 8)}</span>
                </Link>
              </td>
              <td>{incident.service}</td>
              <td><SeverityBadge severity={incident.severity} /></td>
              <td><StatusBadge value={incident.status} dot /></td>
              {!compact ? <td><span className="stage-text">{humanize(incident.agent_state)}</span></td> : null}
              <td className="muted">{compact ? formatShortTime(incident.created_at) : formatDuration(incident.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
