import { formatPercent, humanize } from "../lib/format";
import type { InvestigationHypothesis } from "../types";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

interface InvestigationHypothesisCardProps {
  hypothesis: InvestigationHypothesis;
  onTest?: (hypothesisId: string) => void;
  busy?: boolean;
}

export function InvestigationHypothesisCard({
  hypothesis,
  onTest,
  busy = false
}: InvestigationHypothesisCardProps) {
  return (
    <article className="investigation-hypothesis-card">
      <div className="hypothesis-heading">
        <div>
          <span className="eyebrow">{hypothesis.domain} · {hypothesis.priority} PRIORITY</span>
          <h3>{hypothesis.title}</h3>
        </div>
        <StatusBadge value={hypothesis.status} label={humanize(hypothesis.status)} dot />
      </div>
      <p className="hypothesis-description">{hypothesis.description}</p>
      <div className="confidence-row">
        <div className="confidence-label"><span>Server-scored confidence</span><strong>{formatPercent(hypothesis.confidence)}</strong></div>
        <div className="confidence-track" aria-label={`${Math.round(hypothesis.confidence * 100)}% confidence`}><span style={{ width: `${Math.round(hypothesis.confidence * 100)}%` }} /></div>
      </div>
      <div className="investigation-hypothesis-columns">
        <div><span className="evidence-label"><Icon name="check" size={13} /> Supporting</span><strong>{hypothesis.supporting_evidence.length}</strong></div>
        <div><span className="evidence-label contradicting"><Icon name="close" size={13} /> Contradicting</span><strong>{hypothesis.contradicting_evidence.length}</strong></div>
        <div><span className="evidence-label"><Icon name="search" size={13} /> Evidence gaps</span><strong>{hypothesis.missing_evidence.length}</strong></div>
      </div>
      {hypothesis.next_validation_step ? <div className="hypothesis-next-step"><span className="eyebrow">NEXT VALIDATION STEP</span><p>{hypothesis.next_validation_step}</p></div> : null}
      {onTest && hypothesis.status !== "SUPPORTED" && hypothesis.status !== "REJECTED" ? <button className="secondary-button" type="button" onClick={() => onTest(hypothesis.hypothesis_id)} disabled={busy}><Icon name="verification" size={14} /> {busy ? "Testing…" : "Test with read-only probes"}</button> : null}
    </article>
  );
}
