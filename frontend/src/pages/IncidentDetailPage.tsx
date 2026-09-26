import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getIncident, listIncidentActivity } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import type { ActivityEvent, Incident } from "../types";

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!incidentId) return;
    let active = true;
    Promise.all([getIncident(incidentId), listIncidentActivity(incidentId)])
      .then(([incidentPayload, activityPayload]) => {
        if (!active) return;
        setIncident(incidentPayload);
        setActivity(activityPayload);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load incident");
      });
    return () => {
      active = false;
    };
  }, [incidentId]);

  if (error) {
    return <EmptyState eyebrow="REQUEST FAILED" title="Incident unavailable" description={error} />;
  }

  if (!incident) {
    return <div className="loading-state">Loading incident record…</div>;
  }

  return (
    <section className="page-section">
      <Link className="back-link" to="/incidents">← Back to incidents</Link>
      <div className="page-heading detail-heading">
        <div>
          <span className="eyebrow">INCIDENT RECORD · {incident.id.slice(0, 8)}</span>
          <h1>{incident.title}</h1>
          <p>{incident.description}</p>
        </div>
        <div className="detail-badges">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge value={incident.status} />
        </div>
      </div>

      <div className="detail-grid">
        <div className="surface-card">
          <span className="eyebrow">CONTROL STATE</span>
          <div className="detail-stat"><strong>{incident.agent_state.replace(/_/g, " ")}</strong><span>agent state</span></div>
          <div className="detail-meta"><span>Service</span><strong>{incident.service}</strong></div>
          <div className="detail-meta"><span>Received</span><strong>{formatTime(incident.created_at)}</strong></div>
          <div className="detail-meta"><span>Updated</span><strong>{formatTime(incident.updated_at)}</strong></div>
        </div>
        <div className="surface-card activity-card">
          <div className="card-heading"><span className="eyebrow">ACTIVITY</span><span className="muted">{activity.length} events</span></div>
          {activity.length === 0 ? (
            <EmptyState title="No activity recorded" description="The audit stream is empty for this incident." />
          ) : (
            <ol className="timeline">
              {activity.map((event) => (
                <li key={event.id}>
                  <span className="timeline-dot" />
                  <div><strong>{event.message}</strong><span className="muted">{formatTime(event.created_at)}</span></div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}
