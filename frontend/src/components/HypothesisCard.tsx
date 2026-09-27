import { formatPercent, humanize } from "../lib/format";
import type { Hypothesis } from "../types";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

export function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const percentage = Math.round(hypothesis.confidence * 100);
  return (
    <article className="hypothesis-card">
      <div className="hypothesis-heading">
        <div>
          <span className="eyebrow">HYPOTHESIS</span>
          <h3>{hypothesis.title}</h3>
        </div>
        <StatusBadge value={hypothesis.validation_status} label={humanize(hypothesis.validation_status)} />
      </div>
      <p className="hypothesis-description">{hypothesis.description}</p>
      <div className="confidence-row">
        <div className="confidence-label"><span>Confidence</span><strong>{formatPercent(hypothesis.confidence)}</strong></div>
        <div className="confidence-track" aria-label={`${percentage}% confidence`}><span style={{ width: `${percentage}%` }} /></div>
      </div>
      <div className="evidence-split">
        <div>
          <span className="evidence-label"><Icon name="check" size={13} /> Supporting evidence</span>
          <strong>{hypothesis.supporting_evidence.length}</strong>
        </div>
        <div>
          <span className="evidence-label contradicting"><Icon name="close" size={13} /> Contradicting evidence</span>
          <strong>{hypothesis.contradicting_evidence.length}</strong>
        </div>
      </div>
    </article>
  );
}
