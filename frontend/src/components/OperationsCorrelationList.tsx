import { formatDateTime, humanize } from "../lib/format";
import type { CrossDomainCorrelation } from "../types";
import { StatusBadge } from "./StatusBadge";

export function OperationsCorrelationList({ correlations }: { correlations: CrossDomainCorrelation[] }) {
  if (!correlations.length) {
    return <div className="operations-empty-row">No cross-domain relationships are available from the selected evidence window.</div>;
  }

  return (
    <div className="operations-correlation-list">
      {correlations.map((correlation) => (
        <article className="operations-correlation-row" key={correlation.correlation_id}>
          <div className="operations-correlation-route">
            <span>{correlation.source_domain}</span>
            <span className="operations-correlation-arrow">→</span>
            <span>{correlation.target_domain}</span>
          </div>
          <div className="operations-correlation-copy">
            <div className="operations-correlation-heading">
              <strong>{humanize(correlation.relationship_type)}</strong>
              <StatusBadge value={`${Math.round(correlation.confidence * 100)}%`} label={`${Math.round(correlation.confidence * 100)}% confidence`} />
            </div>
            <p>{correlation.explanation}</p>
            <span className="table-subtext">{correlation.temporal_relationship} · {correlation.evidence_ids.length} evidence reference(s)</span>
          </div>
          <time>{formatDateTime(correlation.source.collected_at)}</time>
        </article>
      ))}
    </div>
  );
}
