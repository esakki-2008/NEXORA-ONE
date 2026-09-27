import { formatShortTime, humanize, formatPercent } from "../lib/format";
import type { CorrelationRecord } from "../types";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";

export function CorrelationList({ correlations }: { correlations: CorrelationRecord[] }) {
  if (!correlations.length) {
    return <EmptyState compact eyebrow="NO CORRELATIONS" title="No explainable relationships yet" description="Correlations appear only when collected evidence shares a supported temporal, service, deployment, configuration, or signal relationship." />;
  }
  return (
    <div className="correlation-list">
      {correlations.map((correlation) => (
        <article className="correlation-row" key={correlation.correlation_id}>
          <span className="correlation-node"><Icon name="activity" size={15} /></span>
          <div className="correlation-body">
            <div className="correlation-title-row"><strong>{humanize(correlation.relationship)}</strong><span>{formatShortTime(correlation.created_at)}</span></div>
            <p>{correlation.reason}</p>
            <div className="correlation-meta"><span>{correlation.evidence_ids.length} evidence records</span><span>{correlation.dimensions.map(humanize).join(" · ")}</span><b>{formatPercent(correlation.strength)} strength</b></div>
          </div>
        </article>
      ))}
    </div>
  );
}
