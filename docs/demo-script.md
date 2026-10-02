# NEXORA ONE — 2–3 minute demo script

## Demo contract

This is a controlled presentation of the reference implementation. Say **“SIMULATED / CONTROLLED DEMONSTRATION”** before opening the ShopFlow fixture and keep that label visible while discussing its evidence or actions. Do not describe the simulator as a production payment system or the in-memory stores as production infrastructure.

The AI boundary is explicit: **Frontend → NEXORA Backend → Nebius Token Factory → NVIDIA Nemotron**. The browser never receives the Nebius credential and never authorizes, approves, executes, verifies, or resolves an action.

Before presenting, configure `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, and `NEBIUS_MODEL` only in the backend runtime and run:

```bash
.venv/bin/python scripts/verify_nebius_runtime.py
.venv/bin/python scripts/run_shopflow_demo.py
```

Only call the provider “verified” when the first command reports an actual successful structured response. If no valid runtime credential is available, use the documented safe-failure wording instead of implying a live result.

## Timed walkthrough

### 0:00–0:20 — Frame the problem and architecture

> “NEXORA ONE is one operations plane for incidents that cross revenue, application, infrastructure, and support boundaries. This workflow is evidence-first and ends only in verified resolution. The inference route is server-side through Nebius Token Factory and NVIDIA Nemotron; the model is an assistive, untrusted planner.”

Point to the Command Center’s enterprise status, active incident intake, and observable AI activity. Explain that the UI shows lifecycle events, not private chain-of-thought.

### 0:20–0:45 — Select the ShopFlow source

Open the ShopFlow **payment-failure** scenario from the Operations or Command Center surface.

> “This card is explicitly **SIMULATED / CONTROLLED DEMONSTRATION**. It contains structured logs, metrics, deployment observations, configuration, and transactions. The simulator API is read-only until a separately registered demonstration action is approved.”

Show the evidence source, impact, and payment signal. State that missing real enterprise adapters are represented as source boundaries rather than invented health.

### 0:45–1:10 — Create the evidence context

Open or create the Payment Service incident, then start the investigation. Show the investigation evidence, provenance, correlations, hypothesis status, and timeline.

> “Evidence is normalized and retained with provenance. Correlation is not presented as causation. The server, not the model or the browser, owns tenant scope and evidence bindings.”

### 1:10–1:35 — Request AI assistance

Use the AI analysis control for the incident. Show the concise lifecycle events:

1. request accepted;
2. evidence normalized;
3. inference started;
4. structured response received;
5. response validated; and
6. recommendation generated, if present.

Show the provider and configured model fields in Settings/AI activity. Do not open or read hidden reasoning. A live response must be a real `POST /api/ai/analyze` result from the configured **Nebius Token Factory / NVIDIA Nemotron** provider. An unconfigured run must remain a safe failure.

### 1:35–1:55 — Review the proposed action

Open Controlled Actions. Show `restart_payment_service`, the server-calculated risk, expected impact, rollback plan, verification strategy, evidence IDs, and immutable fingerprint.

> “The recommendation is only a proposal. The action name and parameters were checked against the registered action catalog. AI output cannot change tenant, risk, policy, approval, execution, verification, or resolution state.”

### 1:55–2:20 — Human approval, controlled action, and proof

Use a distinct human approver to review the exact fingerprint, then execute as an authorized operator. Show:

- approval recorded;
- registered simulator action executed;
- verification checks with expected and actual values;
- hash-chained audit events;
- incident status changing to `resolved` only after verification passes; and
- the generated incident report.

Keep the `SIMULATED / CONTROLLED DEMONSTRATION` label visible. This is controlled in-memory ShopFlow state, not a real payment restart.

### 2:20–2:45 — Failure path and close

Use the existing regression scenario or the failure-path test to show the same boundary when verification fails:

1. verification fails;
2. the captured before-state is used for rollback;
3. a bounded retry is available, not an infinite loop;
4. a successful retry can produce proof; or
5. permanent failure reaches `REQUIRES_HUMAN` and does not generate a false resolution report.

> “NEXORA does not call execution success resolution. Recovery and proof are separate gates, and an unresolved failure is escalated to a human.”

Close with the low-cost deployment path: frontend static hosting, one NEXORA backend service, and a server-side connection to Nebius Token Factory. Name the limitations plainly: reference authentication, in-memory persistence, simulator-only mutating actions, and no production identity, durable audit, or live enterprise adapters.

## Live-provider and fallback wording

If verification succeeds:

> “The structured response was actually returned by the configured NVIDIA Nemotron model through Nebius Token Factory and then validated by the NEXORA AIService. The API key stayed server-side.”

If it is unavailable, say exactly:

> “Live provider verification not executed because no valid runtime credential was available in the environment.”

Do not substitute a fixture, mock, or hardcoded model response for a live-provider claim.
