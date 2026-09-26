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

Evidence and hypothesis reads return empty arrays until a future bounded investigation service records data. The report route returns 404 until an actual report is generated; it never returns placeholder content.

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

## Phase 2 frontend routes

The command center consumes the API above without duplicating backend logic:

- `/command-center` — live intake, backend-sourced AI status/activity, domain boundaries, and simulator coverage;
- `/incidents` and `/incidents/{id}` — filtered incident register and detail;
- `/investigation` and `/investigation/{id}` — structured evidence and hypothesis surfaces;
- `/evidence` — recorded and simulator evidence explorer;
- `/agents`, `/operations`, `/verification`, `/reports`, `/history`, and `/settings` — honest read-only foundations for later phases. Settings provides an explicit provider verification control but never accepts or displays credentials.
