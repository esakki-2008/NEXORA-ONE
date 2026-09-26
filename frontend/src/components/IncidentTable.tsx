import { Link } from "react-router-dom";

import { SeverityBadge, StatusBadge } from "./StatusBadge";
import type { Incident } from "../types";

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function IncidentTable({ incidents }: { incidents: Incident[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Incident</th>
            <th>Service</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Received</th>
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
              <td><StatusBadge value={incident.status} /></td>
              <td className="muted">{formatTime(incident.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
