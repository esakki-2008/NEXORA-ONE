import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfidenceFactors } from "./ConfidenceFactors";
import { CorrelationList } from "./CorrelationList";
import { EvidenceTable, type EvidenceView } from "./EvidenceTable";
import { InvestigationHypothesisCard } from "./InvestigationHypothesisCard";

const evidence: EvidenceView = {
  id: "evidence-1",
  incidentId: "incident-1",
  incidentTitle: "ShopFlow payment investigation",
  type: "LOG",
  source: "SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / Payment Service",
  timestamp: "2026-09-27T10:00:00Z",
  summary: "Gateway authorization failed after retry budget was exhausted",
  relevance: 0.92,
  status: "simulator",
  confidence: 0.9,
  collectedBy: "investigation_tool:get_logs",
  collectionStatus: "COLLECTED",
  rawReference: { execution_id: "execution-1", tool_name: "get_logs" },
  metadata: { simulated: "true" }
};

const hypothesis = {
  hypothesis_id: "hypothesis-1",
  incident_id: "incident-1",
  title: "Payment service failure is supported by aligned operational signals",
  description: "Payment failure signals align in the incident window.",
  domain: "REVENUE",
  supporting_evidence: ["evidence-1"],
  contradicting_evidence: [],
  missing_evidence: ["deployment-specific error signature"],
  confidence: 0.81,
  confidence_factors: { supporting_signals: 0.75 },
  status: "INCONCLUSIVE" as const,
  priority: "HIGH",
  next_validation_step: "Inspect a recent deployment with a read-only probe.",
  created_at: "2026-09-27T10:00:00Z",
  updated_at: "2026-09-27T10:00:00Z"
};

const correlation = {
  correlation_id: "correlation-1",
  incident_id: "incident-1",
  evidence_ids: ["evidence-1", "evidence-2"],
  relationship: "ERROR_METRIC_ALIGNMENT",
  reason: "Error/log signal and metric anomaly align in time; causation remains unconfirmed.",
  dimensions: ["error_signature", "temporal_proximity"],
  strength: 0.84,
  temporal_delta_seconds: 30,
  created_at: "2026-09-27T10:00:00Z"
};

describe("investigation intelligence surfaces", () => {
  it("labels simulator provenance and exposes bounded references", () => {
    const onSelect = vi.fn();
    render(<EvidenceTable records={[evidence]} onSelect={onSelect} />);

    expect(screen.getByText("Synthetic/demo · simulator")).toBeInTheDocument();
    expect(screen.getByText(evidence.source)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: evidence.summary }));
    expect(onSelect).toHaveBeenCalledWith(evidence);
  });

  it("renders non-causal correlation and deterministic confidence factors", () => {
    render(
      <>
        <CorrelationList correlations={[correlation]} />
        <ConfidenceFactors
          confidence={0.81}
          factors={{ supporting_signals: 0.75, missing_evidence_penalty: 0.05 }}
          explanation={["Missing evidence reduced confidence."]}
        />
      </>
    );

    expect(screen.getByText(/causation remains unconfirmed/i)).toBeInTheDocument();
    expect(screen.getByText("81%")).toBeInTheDocument();
    expect(screen.getByText("Missing evidence reduced confidence.")).toBeInTheDocument();
  });

  it("shows hypothesis gaps and invokes read-only testing", () => {
    const onTest = vi.fn();
    render(<InvestigationHypothesisCard hypothesis={hypothesis} onTest={onTest} />);

    expect(screen.getByText("Evidence gaps")).toBeInTheDocument();
    expect(screen.getByText(hypothesis.next_validation_step)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /test with read-only probes/i }));
    expect(onTest).toHaveBeenCalledWith("hypothesis-1");
  });
});
