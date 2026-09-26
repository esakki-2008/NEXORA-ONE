import { useEffect, useState } from "react";

import { listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { IncidentTable } from "../components/IncidentTable";
import type { Incident } from "../types";

export function CommandCenterPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listIncidents()
      .then((payload) => {
        if (active) setIncidents(payload);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load operations feed");
      });
    return () => {
      active = false;
    };
  }, []);

  const openCount = incidents.filter((incident) => !["resolved", "closed", "cancelled"].includes(incident.status)).length;
  const criticalCount = incidents.filter((incident) => incident.severity === "critical").length;
  const humanCount = incidents.filter((incident) => incident.status === "requires_human").length;

  return (
    <section className="page-section">
      <div className="page-heading command-heading">
        <div>
          <span className="eyebrow">COMMAND CENTER / FOUNDATION</span>
          <h1>Operational posture</h1>
          <p>One view of the records currently known to the NEXORA control plane.</p>
        </div>
        <div className="live-marker"><span /> LIVE API FEED</div>
      </div>

      {error ? <EmptyState eyebrow="API UNAVAILABLE" title="Posture is not available" description={error} /> : null}

      <div className="metric-grid">
        <div className="metric-card"><span className="eyebrow">OPEN RECORDS</span><strong>{openCount}</strong><span className="muted">from incident API</span></div>
        <div className="metric-card metric-critical"><span className="eyebrow">CRITICAL</span><strong>{criticalCount}</strong><span className="muted">recorded severity</span></div>
        <div className="metric-card"><span className="eyebrow">HUMAN REVIEW</span><strong>{humanCount}</strong><span className="muted">explicit handoffs</span></div>
        <div className="metric-card"><span className="eyebrow">AGENT STATE</span><strong>BOUND</strong><span className="muted">workflow not enabled</span></div>
      </div>

      <div className="surface-card">
        <div className="card-heading">
          <div><span className="eyebrow">RECENT INTAKE</span><h2>Incident register</h2></div>
          <span className="count-label">{incidents.length} records</span>
        </div>
        {incidents.length === 0 && !error ? (
          <EmptyState title="No active incident records" description="The command center will reflect real API records as they are received." />
        ) : null}
        {incidents.length > 0 ? <IncidentTable incidents={incidents.slice(0, 8)} /> : null}
      </div>
    </section>
  );
}
