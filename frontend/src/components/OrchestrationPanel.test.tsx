import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OrchestrationPanel } from "./OrchestrationPanel";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

const baseContext = {
  incident_id: "incident-1",
  incident: {
    id: "incident-1",
    title: "Payment failure",
    description: "Payment failures increased.",
    severity: "high",
    status: "remediation_proposed",
    service: "Payment Service",
    agent_state: "WAITING_FOR_APPROVAL",
    created_at: "2026-09-26T10:00:00Z",
    updated_at: "2026-09-26T10:02:00Z"
  },
  source_type: "synthetic_demo_data",
  scenario_id: "payment-failure",
  current_state: "WAITING_FOR_APPROVAL",
  runtime_status: "WAITING",
  evidence: [],
  hypotheses: [],
  selected_domain: "REVENUE",
  selected_domains: ["REVENUE"],
  selected_agent: "revenue",
  tool_calls: [],
  tool_results: [],
  risk_level: "HIGH",
  priority: "HIGH",
  priority_factors: {},
  remediation_plan: {
    id: "plan-1",
    problem: "Payment failure",
    steps: [
      {
        id: "step-1",
        sequence: 1,
        action: "restart_payment_service",
        description: "Restart simulator service",
        tool_name: "execute_safe_action",
        parameters: { action_name: "restart_payment_service", parameters: {} },
        risk_level: "HIGH",
        is_change: true,
        requires_approval: true,
        status: "REQUESTED"
      }
    ],
    created_at: "2026-09-26T10:02:00Z"
  },
  approval: {
    approval_id: "approval-1",
    incident_id: "incident-1",
    action_id: "step-1",
    requested_action: "restart_payment_service",
    risk_level: "HIGH",
    reason: "The fixed simulator action requires operator approval.",
    expected_impact: "Restore the simulator payment service.",
    rollback_plan: "Simulator only.",
    requested_at: "2026-09-26T10:02:00Z",
    expires_at: "2026-09-26T10:32:00Z",
    status: "pending",
    approved_by: null,
    approved_at: null,
    rejected_by: null,
    rejected_at: null,
    decision_reason: null
  },
  verification_plan: [],
  verification_results: [],
  verification_outcome: null,
  activity: [
    {
      id: "activity-1",
      incident_id: "incident-1",
      event_type: "orchestrator.approval.requested",
      message: "Action requires approval",
      created_at: "2026-09-26T10:02:00Z",
      metadata: {}
    }
  ],
  transition_history: [],
  errors: [],
  analysis_summary: "Payment evidence supports a bounded simulator response.",
  analysis_confidence: 0.9,
  ai_status: "configured",
  created_at: "2026-09-26T10:00:00Z",
  updated_at: "2026-09-26T10:02:00Z"
};

describe("OrchestrationPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the approval gate and sends decisions to the backend", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    const resolvedContext = {
      ...baseContext,
      current_state: "RESOLVED",
      runtime_status: "COMPLETED",
      approval: { ...baseContext.approval, status: "approved", approved_by: "Local operator" },
      verification_outcome: "VERIFIED"
    };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requests.push({ url, init });
      if (url.endsWith("/api/orchestrator/incidents/incident-1")) return Promise.resolve(jsonResponse(baseContext));
      if (url.endsWith("/api/simulator/scenarios")) return Promise.resolve(jsonResponse([]));
      if (url.endsWith("/approve")) return Promise.resolve(jsonResponse(resolvedContext));
      return Promise.resolve(jsonResponse({ detail: "unexpected request" }, 404));
    }));

    render(<OrchestrationPanel incidentId="incident-1" />);

    expect(await screen.findByText("APPROVAL GATE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve and execute/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /approve and execute/i }));

    await waitFor(() => expect(screen.getByText("Verification Verified")).toBeInTheDocument());
    const approvalRequest = requests.find((request) => request.url.endsWith("/approve"));
    expect(approvalRequest?.init?.body).toContain("Local operator");
  });
});
