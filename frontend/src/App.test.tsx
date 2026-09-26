import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { BrowserRouter } from "react-router-dom";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

describe("NEXORA ONE application shell", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/command-center");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/health")) {
          return Promise.resolve(
            jsonResponse({
              status: "ok",
              service: "NEXORA ONE API",
              environment: "test",
              timestamp: new Date().toISOString()
            })
          );
        }
        return Promise.resolve(jsonResponse([]));
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders navigation and an honest empty command center", async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    expect(screen.getByText((_, element) => element?.classList.contains("brand-name") ?? false)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /incidents/i })).toBeInTheDocument();
    expect(await screen.findByText("No active incident records")).toBeInTheDocument();
  });
});
