# NEXORA ONE API notes

The API contains the Phase 1/2 incident and simulator surfaces plus the Phase 3 server-side Nebius/NVIDIA AI boundary. Provider credentials are accepted only by the backend environment; no frontend request includes `NEBIUS_API_KEY`.

Run the API with:

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

OpenAPI is available at `/docs` and `/redoc`.

## Create an incident

```http
POST /api/incidents
Content-Type: application/json
```

```json
{
  "title": "Checkout error rate increased",
  "description": "Users are seeing failed checkout requests.",
  "severity": "high",
  "service": "Checkout Service"
}
```

The response contains a generated UUID, timestamps, `open` incident status, and `INCIDENT_RECEIVED` agent state. The only initial activity event is the real intake audit event.

## Nested resources

Incident evidence and hypothesis routes expose the legacy repository contract. Phase 5 investigation routes provide the richer provenance-preserving records, correlations, server-scored hypotheses, confidence factors, gaps, root-cause candidates, and timeline described in [investigation.md](investigation.md). The report route returns 404 until an actual report is generated; it never returns placeholder content.

## Simulator

`GET /api/simulator/scenarios` returns scenario metadata. `GET /api/simulator/scenarios/{scenario_id}` returns a validated, read-only ShopFlow fixture. Loading a scenario does not create an incident or mutate repository state. The Phase 2 Evidence Explorer labels these observations as `Simulator` and keeps them distinct from persisted incident evidence.

`payment-failure` remains explicitly synthetic/demo data. It is safe to submit to the Phase 3 analysis route for integration testing, but its origin remains visible in the AI prompt context and must not be represented as a live incident.

## Phase 3 AI routes

### `GET /api/ai/health`

Returns the backend's safe view of Nebius readiness:

```json
{
  "provider": "nebius",
  "model": "nvidia/nemotron-ultra",
  "status": "configured",
  "verified": false,
  "message": "Provider configuration is present; connectivity has not been verified.",
  "last_verified_at": null
}
```

`verified: true` is set only after a real Nebius Token Factory request returns a response that passes the NEXORA structured schema. A configured-but-unverified provider is not displayed as `CONNECTED`. The API never returns the base URL, API key, request headers, or provider response body.

Possible statuses include `not_configured`, `configured`, `authentication_failed`, `model_unavailable`, `provider_unavailable`, `timeout`, and `error`.

### `POST /api/ai/test`

Makes a real, minimal structured request to the configured NVIDIA Nemotron model. There is no synthetic success path. The response is safe and concise:

```json
{
  "success": true,
  "status": "configured",
  "message": "Nebius Token Factory and NVIDIA Nemotron verification succeeded.",
  "response": {
    "status": "analysis_complete",
    "current_step": "resolved",
    "summary": "...",
    "selected_tools": [],
    "evidence": [],
    "hypotheses": [],
    "validated_hypothesis": null,
    "recommendation": null,
    "risk_level": "READ_ONLY",
    "requires_approval": true,
    "verification_plan": [],
    "confidence": 0.8
  }
}
```

A provider failure returns HTTP 200 with `success: false` for this verification control, together with a safe status/message. Analysis routes use failure HTTP statuses so callers can distinguish a rejected analysis from a valid response.

### `POST /api/ai/analyze`

Submit exactly one source:

```json
{ "incident_id": "2dc4c8c3-5d36-44a5-83ac-0f01e8b39f4d" }
```

or:

```json
{ "scenario_id": "payment-failure" }
```

Live incident requests read the incident, recorded evidence, hypotheses, and activity through the repository. Scenario requests load a read-only `ShopFlowSimulator` fixture and carry `data_classification: synthetic_demo_data`. The service does not invent missing records or create an incident from a fixture.

The only accepted provider output is `AIAnalysisResponse`. Evidence references and hypothesis citation IDs must exist in the source evidence index; the backend copies source and summary from that trusted index before returning them. The accepted envelope has these validated fields:

- `status` and `current_step`;
- concise `summary`;
- allow-listed `selected_tools` proposals, with catalog-matched risk metadata;
- evidence references and hypotheses;
- optional `validated_hypothesis`;
- optional `recommendation`;
- `risk_level` and `requires_approval`;
- `verification_plan`;
- bounded `confidence`.

The response is data only. Phase 3 does not execute selected tools, shell commands, Python, remediation, rollback, or production changes. Risky recommendations are rejected unless approval is explicitly required.

### `GET /api/ai/activity`

Returns concise AI lifecycle events, newest first. Use `?incident_id=<uuid>` to filter events for a live incident. Event examples include `ai.request.accepted`, `ai.evidence.normalized`, `ai.inference.started`, `ai.response.received`, `ai.response.validated`, `ai.recommendation.generated`, and `ai.inference.failed`. Events do not include prompts, completions, chain-of-thought, API keys, or provider response bodies.

## Provider configuration and failure behavior

The backend reads:

| Variable | Default | Notes |
| --- | --- | --- |
| `NEBIUS_API_KEY` | none | Required server-only secret |
| `NEBIUS_BASE_URL` | none | Required; use the Nebius Token Factory OpenAI-compatible base URL, normally ending in `/v1/` |
| `NEBIUS_MODEL` | none | Required NVIDIA Nemotron model identifier |
| `NEBIUS_TIMEOUT_SECONDS` | `60` | Positive request timeout |
| `NEBIUS_MAX_RETRIES` | `2` | Bounded retry count for transient timeout/network/408/429/5xx failures |

The adapter sends `Authorization: Bearer <server secret>`, `response_format: {"type":"json_object"}`, and the configured model to `<NEBIUS_BASE_URL>/chat/completions`. It never logs the authorization header.

Failure mapping is intentionally generic:

| Condition | AI status | Analysis HTTP behavior |
| --- | --- | --- |
| Missing key/base URL/model | `not_configured` | 503 |
| 401/403 from Nebius | `authentication_failed` | 502 |
| 404 configured model/endpoint | `model_unavailable` | 503 |
| network/provider/5xx exhaustion | `provider_unavailable` | 503 |
| request timeout or 408 exhaustion | `timeout` | 504 |
| malformed JSON or schema-invalid response | `error` | 502 |
| other provider 4xx rejection | `error` | 502 |

Provider tests use `httpx.MockTransport`; the test suite never requires live credentials.

## Phase 5 investigation routes

Investigation is a separate evidence workflow that reuses the Phase 4 read-only tool runtime and calls the existing orchestrator only at the guarded handoff boundary. Start accepts an optional `scenario_id`, an idempotency `request_id`, and `auto_handoff`:

```http
POST /api/investigations/incidents/{incident_id}/start
Content-Type: application/json
```

```json
{
  "scenario_id": "payment-failure",
  "request_id": "shopflow-payment-demo-1",
  "auto_handoff": false
}
```

Controlled ShopFlow evidence is returned with `source_type: "SIMULATED / CONTROLLED DEMONSTRATION"`, `simulated: true`, collector metadata, collection status, and bounded raw references. The five supported scenarios are `payment-failure`, `database-failure`, `latency-spike`, `bad-deployment`, and `configuration-mismatch`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/investigations` | List investigation summaries |
| `POST` | `/api/investigations/incidents/{id}/start` | Start or return an idempotent investigation |
| `GET` | `/api/investigations/incidents/{id}` | Retrieve the investigation for an incident |
| `GET` | `/api/investigations/{id}` | Retrieve the complete context |
| `GET` | `/api/investigations/{id}/summary` | Retrieve a compact summary |
| `GET` | `/api/investigations/{id}/evidence` | Retrieve normalized evidence |
| `GET` | `/api/investigations/{id}/correlations` | Retrieve explainable relationships |
| `GET` | `/api/investigations/{id}/hypotheses` | Retrieve server-scored candidates |
| `GET` | `/api/investigations/{id}/timeline` | Retrieve the audit timeline |
| `POST` | `/api/investigations/{id}/collect` | Collect additional allow-listed evidence |
| `POST` | `/api/investigations/{id}/test-hypothesis` | Test one hypothesis with bounded probes |
| `POST` | `/api/investigations/{id}/handoff` | Hand off to Phase 4 orchestration |
| `POST` | `/api/investigations/{id}/cancel` | Cancel without executing a tool |

A live incident with no recorded evidence becomes `REQUIRES_HUMAN`; no evidence or confidence is fabricated. Handoff does not approve or execute an action and cannot mark an incident resolved. The Phase 4 orchestrator remains the only owner of risk policy, approval, controlled action, verification, and resolution.

## Phase 6 operations routes

Operations is one server-generated intelligence boundary across eight domains. Every response includes source/provenance metadata. With no `scenario_id` or recorded incident source, domains are `NOT_CONFIGURED`; no values are inferred from absence. With an explicit ShopFlow scenario, simulator-derived values carry `SIMULATED / CONTROLLED DEMONSTRATION`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/operations/snapshot` | Unified snapshot; accepts optional `scenario_id` and `incident_id` |
| `POST` | `/api/operations/refresh` | Manual refresh of the same snapshot context |
| `GET` | `/api/operations/domains` | Health for IT, REVENUE, SUPPORT, SUPPLY_CHAIN, CONTRACTS, CLOUD, DATA, COMPLIANCE |
| `GET` | `/api/operations/domains/{domain}` | Domain metrics, service health, signals, related incidents/evidence, impact, and correlations |
| `GET` | `/api/operations/signals` | Operational signals, optionally filtered with `domain`, `scenario_id`, or `incident_id` |
| `GET` | `/api/operations/signals/{id}` | One bounded signal |
| `POST` | `/api/operations/signals/{id}/investigate` | Start/open Phase 5 investigation; never executes remediation |
| `GET` | `/api/operations/correlations` | Cross-domain related-signal records |
| `GET` | `/api/operations/priorities` | Explainable deterministic priority items |
| `GET` | `/api/operations/business-impact` | Deterministic business-impact calculation |
| `GET` | `/api/operations/health` | Source availability and configured-domain status |

Example controlled snapshot:

```http
GET /api/operations/snapshot?scenario_id=payment-failure
```

The response contains eight domain records, simulator-labeled source metadata, critical signals, a bounded transaction/customer estimate, related-signal correlations, and server-owned priority factors. Correlations explicitly remain relationships and are not proof of causation. The payment signal's Investigate action creates or opens a Phase 5 context, and any later remediation remains behind the Phase 4 orchestrator's policy, approval, controlled-action, verification, and resolution rules.

## Phase 7 controlled actions routes

Phase 7 exposes one server-owned action lifecycle. All mutations are bound to a live incident record and an explicit ShopFlow scenario; the response never claims production control.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/actions/registry` | List the seven fixed action definitions and strict parameter JSON schemas |
| `GET` | `/api/actions` | List controlled action records; optional `status` filter |
| `POST` | `/api/actions` | Create a planner-generated, fingerprinted proposal |
| `GET` | `/api/actions/{action_id}` | Retrieve lifecycle state, binding, fingerprint, rollback, and verification metadata |
| `POST` | `/api/actions/{action_id}/approve` | Record explicit authorized human approval for the exact fingerprint |
| `POST` | `/api/actions/{action_id}/reject` | Reject and escalate a pending action |
| `POST` | `/api/actions/{action_id}/execute` | Execute an approved registered action with bounded retry/timeout and verification |
| `POST` | `/api/actions/{action_id}/cancel` | Cancel before execution |
| `POST` | `/api/actions/{action_id}/rollback` | Restore captured before-state and verify rollback |
| `GET` | `/api/actions/{action_id}/audit` | Return the append-only hash-chained audit events |
| `GET` | `/api/actions/{action_id}/verification` | Return before/after state and verification/rollback status |

Create requests accept only incident/investigation/scenario identifiers, a registered action recommendation/name, strict parameters, a bounded requester field, and an idempotency key. Risk, normalized values, rollback metadata, fingerprint, approval, execution, verification, and audit references are server-owned. AI actors cannot approve or execute; high-risk actions reject `auto_execute`. Unknown action names, extra parameters, changed fingerprints, wrong bindings, expired approvals, unauthorized actors, and duplicate executions fail closed.

The payment-failure happy path is: create a Payment Service incident, investigate or hand off through the existing Phase 5/4 services, `POST /api/actions` with `restart_payment_service`, approve as a human, execute, inspect verification, then retrieve the generated incident report. The action service resolves the incident only after verification passes. Failed verification uses the captured simulator snapshot for rollback and escalates if rollback cannot be verified.

See [actions.md](actions.md) for the state machine, registry contract, safety model, and examples.

## Frontend routes

The command center consumes the API above without duplicating backend logic:

- `/command-center` — live intake, backend-sourced AI status/activity, domain boundaries, and simulator coverage;
- `/incidents` and `/incidents/{id}` — filtered incident register and detail;
- `/investigation` and `/investigation/{id}` — structured evidence and hypothesis surfaces;
- `/evidence` — recorded and simulator evidence explorer;
- `/agents`, `/operations`, `/verification`, `/reports`, `/history`, and `/settings` — honest read-only foundations with server-owned controls. Settings provides an explicit provider verification control but never accepts or displays credentials;
- `/remediation` — Controlled Actions registry, proposal and approval queue;
- `/remediation/{actionId}` — exact action fingerprint, approval, execution/rollback, verification, and audit detail.
