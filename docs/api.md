# Phase 1 API notes

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

## Phase 2 frontend routes

The command center consumes the API above without duplicating backend logic:

- `/command-center` — live intake, observable activity, domain boundaries, and simulator coverage;
- `/incidents` and `/incidents/{id}` — filtered incident register and detail;
- `/investigation` and `/investigation/{id}` — structured evidence and hypothesis surfaces;
- `/evidence` — recorded and simulator evidence explorer;
- `/agents`, `/operations`, `/verification`, `/reports`, `/history`, and `/settings` — honest read-only foundations for later phases.
