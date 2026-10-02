import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { OperationsCorrelationList } from "./OperationsCorrelationList";
import { OperationsDomainHealthGrid } from "./OperationsDomainHealthGrid";
import { OperationsImpactPanel } from "./OperationsImpactPanel";
import type { BusinessImpact, CrossDomainCorrelation, DomainHealth } from "../types";

const source = {
  source_type: "SIMULATOR" as const,
  source_name: "ShopFlow enterprise operations simulator",
  label: "SIMULATED / CONTROLLED DEMONSTRATION",
  collected_at: "2026-09-27T10:00:00Z",
  availability: "AVAILABLE" as const,
  simulator: true
};

const impact: BusinessImpact = {
  impact_level: "HIGH",
  affected_domains: ["IT", "REVENUE", "SUPPORT"],
  affected_services: ["Payment Service"],
  estimated_customer_impact: 42,
  estimated_revenue_impact: 149.99,
  currency: "USD",
  operational_scope: "3 affected domains, 1 service",
  duration_minutes: 18,
  explanation: ["Controlled demonstration estimate."],
  source,
  simulator: true
};

const domains: DomainHealth[] = [
  {
    domain: "IT",
    status: "DEGRADED",
    health_score: 60,
    active_signals: ["signal-1"],
    critical_signals: [],
    business_impact: {
      impact_level: "HIGH",
      affected_customers: null,
      estimated_revenue_impact: null,
      currency: null,
      explanation: "Synthetic signal",
      source,
      simulator: true
    },
    last_updated: "2026-09-27T10:00:00Z",
    source,
    simulator: true,
    service_health: []
  },
  {
    domain: "DATA",
    status: "NOT_CONFIGURED",
    health_score: null,
    active_signals: [],
    critical_signals: [],
    business_impact: {
      impact_level: "UNKNOWN",
      affected_customers: null,
      estimated_revenue_impact: null,
      currency: null,
      explanation: "No source",
      source: { ...source, source_type: "NOT_CONFIGURED", source_name: "No connected source", label: "NOT_CONFIGURED", availability: "NOT_CONFIGURED", simulator: false },
      simulator: false
    },
    last_updated: null,
    source: { ...source, source_type: "NOT_CONFIGURED", source_name: "No connected source", label: "NOT_CONFIGURED", availability: "NOT_CONFIGURED", simulator: false },
    simulator: false,
    service_health: []
  }
];

const correlation: CrossDomainCorrelation = {
  correlation_id: "correlation-1",
  source_domain: "IT",
  target_domain: "REVENUE",
  source_signal: "signal-1",
  target_signal: "signal-2",
  relationship_type: "BUSINESS_IMPACT",
  temporal_relationship: "Observed in the same window.",
  confidence: 0.88,
  explanation: "Related signals only; not proof of causation.",
  evidence_ids: ["evidence-1"],
  simulator: true,
  source
};

describe("Phase 6 operations intelligence surfaces", () => {
  it("renders configured and not-configured domain health without inventing scores", () => {
    render(<MemoryRouter><OperationsDomainHealthGrid domains={domains} /></MemoryRouter>);
    expect(screen.getByText("IT Operations")).toBeInTheDocument();
    expect(screen.getByText(/not configured/i)).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders correlations as related signals rather than causation", () => {
    render(<OperationsCorrelationList correlations={[correlation]} />);
    expect(screen.getByText(/not proof of causation/i)).toBeInTheDocument();
    expect(screen.getByText("88% confidence")).toBeInTheDocument();
  });

  it("renders simulator business impact labels and bounded estimates", () => {
    render(<OperationsImpactPanel impact={impact} />);
    expect(screen.getAllByText(/simulator estimate/i)).toHaveLength(2);
    expect(screen.getByText("149.99 USD")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
