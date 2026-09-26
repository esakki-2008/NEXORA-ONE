import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { BrowserRouter, MemoryRouter } from "react-router-dom";

const incident = {
  id: "incident-1",
  title: "Payment API Failure",
  description: "Payment authorization failures increased.",
  severity: "critical",
  status: "open",
  service: "Payment Service",
  agent_state: "INCIDENT_RECEIVED",
  created_at: "2026-09-26T10:00:00Z",
  updated_at: "2026-09-26T10:00:00Z"
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function reportResponse() {
  return {
    id: "report-1",
    incident_id: "incident-1",
    summary: "Payment API report",
    root_cause: "No root cause recorded.",
    impact: "No impact recorded.",
    timeline: [],
    actions: [],
    verification: [],
    final_status: "open",
    created_at: "2026-09-26T10:10:00Z"
  };
}

describe("NEXORA ONE application shell", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/command-center");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/health") {
          return Promise.resolve(jsonResponse({
            status: "ok",
            service: "NEXORA ONE API",
            environment: "test",
            timestamp: "2026-09-26T10:00:00Z"
          }));
        }
        if (url.endsWith("/api/ai/health")) {
          return Promise.resolve(jsonResponse({
            provider: "nebius",
            model: "not configured",
            status: "not_configured",
            verified: false,
            message: "Nebius AI is not configured.",
            last_verified_at: null
          }));
        }
        if (url.endsWith("/api/ai/activity")) return Promise.resolve(jsonResponse([]));
        if (url.endsWith("/api/incidents")) return Promise.resolve(jsonResponse([incident]));
        if (url.endsWith("/activity") || url.endsWith("/evidence") || url.endsWith("/hypotheses")) return Promise.resolve(jsonResponse([]));
        if (url.endsWith("/report")) return Promise.resolve(jsonResponse(reportResponse()));
        if (url.includes("/api/incidents/")) return Promise.resolve(jsonResponse(incident));
        if (url.endsWith("/api/simulator/scenarios")) return Promise.resolve(jsonResponse([]));
        return Promise.resolve(jsonResponse([]));
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders navigation and a real-data command center", async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    expect(screen.getByText((_, element) => element?.classList.contains("brand-name") ?? false)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /incidents/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Enterprise Operations Command Center" })).toBeInTheDocument();
    expect(await screen.findByText("Payment API Failure")).toBeInTheDocument();
  });

  it.each([
    ["/command-center", "Enterprise Operations Command Center"],
    ["/incidents", "Incidents"],
    ["/incidents/incident-1", "Payment API Failure"],
    ["/investigation", "Investigation workspace"],
    ["/investigation/incident-1", "Payment API Failure"],
    ["/evidence", "Evidence explorer"],
    ["/agents", "Agent directory"],
    ["/operations", "Unified operations"],
    ["/verification", "Verification center"],
    ["/reports", "Reports"],
    ["/reports/incident-1", "Payment API Failure"],
    ["/history", "Incident history"],
    ["/settings", "Settings"]
  ])("loads the %s route", async (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
