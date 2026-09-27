import { formatPercent, humanize } from "../lib/format";

interface ConfidenceFactorsProps {
  confidence: number;
  factors: Record<string, number>;
  explanation: string[];
}

export function ConfidenceFactors({ confidence, factors, explanation }: ConfidenceFactorsProps) {
  const entries = Object.entries(factors);
  return (
    <div className="confidence-factors">
      <div className="confidence-hero"><span className="eyebrow">EVIDENCE-GROUNDED CONFIDENCE</span><strong>{formatPercent(confidence)}</strong><span>Deterministic server score · not an unvalidated model claim</span></div>
      {entries.length ? <div className="factor-grid">{entries.map(([name, value]) => <div className="factor-row" key={name}><span>{humanize(name)}</span><b>{formatPercent(value)}</b><div className="factor-track"><span style={{ width: `${Math.round(value * 100)}%` }} /></div></div>)}</div> : null}
      {explanation.length ? <ul className="confidence-explanation">{explanation.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : null}
    </div>
  );
}
