import { useCallback, useEffect, useState } from "react";

import { listIncidents } from "../api/incidents";
import { EmptyState } from "../components/EmptyState";
import { IncidentTable } from "../components/IncidentTable";
import type { Incident } from "../types";

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listIncidents()
      .then(setIncidents)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load incidents"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <span className="eyebrow">OPERATIONS / INTAKE</span>
          <h1>Incidents</h1>
          <p>Review incident records received by the NEXORA control plane.</p>
        </div>
        <button className="secondary-button" type="button" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh feed"}
        </button>
      </div>

      <div className="surface-card">
        <div className="card-heading">
          <div><span className="eyebrow">LIVE API FEED</span><h2>Incident register</h2></div>
          <span className="count-label">{loading ? "—" : incidents.length} records</span>
        </div>
        {loading ? <div className="loading-state">Loading incident register…</div> : null}
        {error ? <EmptyState eyebrow="REQUEST FAILED" title="Feed unavailable" description={error} /> : null}
        {!loading && !error && incidents.length === 0 ? (
          <EmptyState title="No incidents received" description="New records will appear here when they are submitted through the API." />
        ) : null}
        {!loading && !error && incidents.length > 0 ? <IncidentTable incidents={incidents} /> : null}
      </div>
    </section>
  );
}
