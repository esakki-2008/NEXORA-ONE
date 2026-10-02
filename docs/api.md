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
{ "incident_id": "2dc4c8c3-5d36-44a5-84ac-0f01e8b39f4d" }
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

## Phase 8 verification API

Phase 8 adds a single `/api/verification` surface that extends the existing action verification boundary. All state, expected/actual values, risk, policy, action identity, trust, confidence, and resolution fields are server-owned.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/verification` | List integrity-checked records; filter with `status`, `incident_id`, or `action_id` |
| `GET` | `/api/verification/summary` | Return total, active, passed, recovery, human-review, cancellation, and success-rate counts |
| `POST` | `/api/verification` | Create a pending record from an existing server-known action ID |
| `GET` | `/api/verification/{verification_id}` | Return one bound Phase 8 record |
| `POST` | `/api/verification/{verification_id}/run` | Run exactly one bounded verification attempt |
| `POST` | `/api/verification/{verification_id}/retry` | Run the next bounded retry using deterministic backoff |
| `POST` | `/api/verification/{verification_id}/cancel` | Cancel a safe non-terminal verification |
| `GET` | `/api/verification/{verification_id}/evidence` | Return expected/actual, provenance, trust, collector, and timestamped evidence |
| `GET` | `/api/verification/{verification_id}/timeline` | Return the append-only event timeline and hash links |

The request models accept only `action_id` plus an authorized operator identity for create/run/retry/cancel and an optional human reason. They reject extra fields. A browser cannot submit actual state, expected state, confidence, trust, status, max attempts, risk, authorization, recovery action, approval, action body, or resolution state.

A normal controlled action execution automatically creates and runs its bound Phase 8 record. The route is useful for inspection and explicit bounded retry/cancellation. Duplicate action creation returns the existing verification; duplicate/concurrent runs are rejected safely. Wrong-incident/action/fingerprint records, stale/untrusted/contradictory evidence, modified records, invalid transitions, cancelled actions, and terminal proof misuse return a conflict rather than widening authority.

Example safe requests:

```json
POST /api/verification/{verification_id}/retry
{
  "requested_by": "Local operator",
  "reason": "Reviewing the first inconclusive simulator observation."
}
```

```json
POST /api/verification/{verification_id}/cancel
{
  "requested_by": "Local operator",
  "reason": "Stop review without claiming recovery."
}
```

The response record includes the full server-owned expected state, actual state, checks, evidence IDs, confidence factors, failure/recovery metadata, action fingerprint, timestamps, and integrity hash. `/api/actions/{action_id}/verification` exposes the same Phase 8 record in the existing action detail contract. `/api/incidents/{incident_id}/evidence` includes copied Phase 8 evidence after controlled action execution, and resolved reports include the proof record rather than a boolean execution claim.

## Phase 9 authentication and authorization

Except for the liveness-only `GET /health`, every `/api/*` request requires a server-issued reference bearer session:

```http
Authorization: Bearer <reference-session>
```

The server validates the signature, subject, tenant, roles, issue time, expiry, token size, and token schema before route logic. The reference token is minted only by the server-side `SecurityService.issue_reference_token()` bootstrap/test hook; there is no public token-minting route. Production must replace this hook with an enterprise identity provider and set `SECURITY_AUTH_SECRET` through a secret manager.

`401` means there is no valid authenticated session. `403` means the authenticated principal lacks the route permission or the supplied actor does not match the principal. `404` is used for resources outside the principal tenant as well as absent resources. Request bodies cannot grant roles, choose a tenant, set risk, approve an action, mark evidence trusted, set verification state, or resolve an incident.

## Phase 9 security routes

| Method | Path | Required permission | Behavior |
| --- | --- | --- | --- |
| `GET` | `/api/security/session` | authenticated | Return subject, tenant, roles, auth state, expiry; never the token |
| `GET` | `/api/security/events` | `ADMIN` / `VIEW_SECURITY_EVENTS` | Return only the principal tenant's structured events after chain verification |
| `GET` | `/api/security/config` | `ADMIN` / `MANAGE_SECURITY` | Return safe limits/origins/rate buckets; never secrets |
| `GET` | `/api/security/integrity` | `ADMIN` / `VIEW_SECURITY_EVENTS` | Return the security-event chain status and tenant scope |

## Server-side resource rules

Incidents, evidence, investigations, actions, approvals, orchestrations, verifications, reports, AI activity, audit records, and security events are tenant-bound. The server passes `principal.tenant_id` to repository/service/store operations and repeats exact incident/action/verification relationships before mutations. AI activity and security events are filtered by tenant; action audits and verification timelines are reached only after the owning action/verification passes the scope check.

Privileged request actors are bound to the authenticated subject for action creation/approval/execution/rollback/cancellation, investigation cancellation, orchestrator approval/rejection/cancellation, Operations investigation, and verification controls. If the actor field is omitted where the endpoint supports omission, the server supplies the authenticated subject rather than trusting a client default.

## Request and error boundary

The middleware rejects malformed/oversized declared `Content-Length` values and counts streamed request chunks against `SECURITY_MAX_REQUEST_BYTES` (default 256 KiB). Pydantic `extra="forbid"` models reject unknown request fields. Sensitive route budgets return `429` and `Retry-After`; provider failures return typed generic messages. Responses include restrictive security headers and CORS accepts only explicit configured origins; wildcard origins are rejected.

## AI, evidence, and execution boundary

AI inputs are framed as untrusted data. Prompt-injection indicators are recorded, but detection is not treated as authorization. Evidence references must be present in the server-built index. Selected tools must be registered, match server metadata, pass their strict input model, and remain tenant/incident bound. Nested actions are checked against the fixed public action registry. AI output cannot approve, execute, set risk/tenant/policy, fabricate evidence, mark verification passed, or resolve an incident.

Only `ToolRegistry` tools and the seven `ActionRegistry` actions can reach the simulator. Unknown tool/action names, commands, callables, module names, filesystem paths, shell/process execution, dynamic imports, `eval`, and `exec` are not accepted. All simulator responses retain `SIMULATED / CONTROLLED DEMONSTRATION` labeling.

## Integrity and security events

Action audit trails, verification records/timelines, and security events are append-oriented and hash-checked. `GET /api/actions/{id}/audit`, verification history routes, and security event routes fail safely with `409` on tamper detection. Events use bounded redacted metadata and include event type, actor, tenant, resource, source, result, and chain links; tokens, provider bodies, prompts, completions, and private reasoning are not logged.

## API security examples

```bash
# Unauthenticated API request: 401
curl -i http://localhost:8000/api/incidents

# Authenticated reference request (token is injected out-of-band)
curl -H "Authorization: Bearer ${NEXORA_REFERENCE_TOKEN}" \
  http://localhost:8000/api/incidents

# A cross-tenant ID is intentionally indistinguishable from an absent ID
curl -H "Authorization: Bearer ${NEXORA_REFERENCE_TOKEN}" \
  http://localhost:8000/api/incidents/<id-from-another-tenant>
```

Never place a real production bearer session in source control, frontend build-time configuration, issue text, logs, or documentation. See [security.md](security.md) and [threat-model.md](threat-model.md).
