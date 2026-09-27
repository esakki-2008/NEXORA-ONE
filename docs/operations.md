# Phase 6 — Enterprise Operations Intelligence

Phase 6 adds a unified, informational operations layer above the Phase 1–5 contracts. It does not create eight independent applications and it does not create a second investigation engine or action path.

```text
OBSERVE → UNDERSTAND → CORRELATE → PRIORITIZE → INVESTIGATE
                                                    ↓
                         Phase 5 investigation → Phase 4 orchestrator
                         plan → approval → controlled action → verify → report
```

## Unified model

The implementation lives under `backend/app/operations/`:

- `context.py` — strict public contracts and source/provenance models;
- `service.py` — one snapshot engine used by all operations endpoints;
- `health.py` — deterministic domain health calculation;
- `metrics.py` — bounded ratios and simulator metric calculations;
- `signals.py` — stable identifiers, evidence references, and source metadata;
- `correlations.py` — deterministic cross-domain related-signal relationships;
- `priorities.py` — explainable server-owned priority scores;
- `snapshots.py` — source availability, snapshot identity, and overall status;
- `domains.py` — domain ordering, labels, and criticality constants.

The eight domain values are `IT`, `REVENUE`, `SUPPORT`, `SUPPLY_CHAIN`, `CONTRACTS`, `CLOUD`, `DATA`, and `COMPLIANCE`. Every domain is returned in a snapshot. A domain without a connected source is `NOT_CONFIGURED` with a null health score; missing data is never converted into zero or healthy.

Public objects carry `SourceMetadata`, including source type/name, collection time, availability, and `simulator`. Controlled records use the visible label:

```text
SIMULATED / CONTROLLED DEMONSTRATION
```

## Domain coverage

### IT Operations

IT combines active incident records and Phase 5 repository evidence when an incident is selected or recorded. For a ShopFlow fixture it derives service health, error/latency metrics, logs, deployment observations, and configuration mismatch signals from the existing read-only simulator. It does not duplicate incident or investigation storage.

### Revenue

Payment transactions provide deterministic transaction volume, successful/failed counts, payment success/failure ratios, and estimated failed-transaction exposure. The estimate preserves the simulator currency and is never converted or presented as financial reporting.

### Customer Support

The payment fixture includes an explicit synthetic support observation with ticket volume, unresolved tickets, escalation rate, response/resolution times, sentiment, affected customers, and issue categories. The operations layer shows a relationship between payment, checkout, and support signals; it does not assert causation.

### Supply Chain

The bounded simulator exposes inventory level, delayed shipments, order backlog, fulfillment delay, supplier/watch risk, and stockout risk. It is operational demonstration data, not an external supply-chain feed.

### Contracts

The simulator exposes operational renewal, vendor dependency, SLA/documentation watch signals, and days remaining. These are reminders and dependency signals only; no legal advice or legal conclusion is produced.

### Cloud

The simulator exposes compute utilization, availability, unused resources, deployment posture, and estimated cost. Cost values are explicitly simulator estimates and not billing data.

### Data

The simulator exposes freshness, completeness, duplicate rate, schema violations, and pipeline failures for a synthetic customer dataset. Ratios are bounded and source-labeled.

### Compliance

The simulator exposes policy/control findings, overdue reviews, audit-evidence/documentation gaps, and access-review-style operational status. Findings are synthetic operational tracking signals, not legal conclusions or compliance certification.

## Health and impact

`DomainHealth` includes status, optional 0–100 health score, active/critical signal identifiers, service health, business-impact summary, timestamp, and source. Status values are:

- `HEALTHY` — connected source with no active signal;
- `DEGRADED` — connected high-severity service signal;
- `WARNING` — connected medium/low active or watch signal;
- `CRITICAL` — connected critical signal;
- `UNKNOWN` — source boundary failed or has insufficient usable data;
- `NOT_CONFIGURED` — no source is connected.

The business-impact engine uses server evidence only: severity, active signal scope, affected services, support customer estimate, transaction failure exposure, and duration. It returns impact level, affected domains/services, bounded customer/revenue values, currency, scope, and explanation. Negative, non-finite, or mixed-currency estimates are rejected or left unavailable. Unrelated baseline simulator signals are visible in their own domains but are not automatically included in the ShopFlow payment incident impact scope.

## Correlation and priority

`CrossDomainCorrelation` includes source/target domains and signals, relationship type, temporal relationship, confidence, explanation, evidence identifiers, and source. The known ShopFlow payment relationships are represented as `BUSINESS_IMPACT`, `TEMPORAL`, and `SERVICE_DEPENDENCY` related-signal records. Each explanation explicitly says the relationship is not proof of causation.

`PriorityItem` is calculated by `priorities.py` from severity, business impact, customer/revenue exposure, affected scope, source confidence, domain criticality, and urgency. Factors are returned with every priority. Nemotron/AI output is not used as an authoritative ranking source.

## APIs

All routes use the same `OperationsService` snapshot assembly:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/operations/snapshot` | Unified eight-domain snapshot; optional `scenario_id`/`incident_id` |
| `POST` | `/api/operations/refresh` | Explicit manual refresh with the same optional context |
| `GET` | `/api/operations/domains` | All domain-health records |
| `GET` | `/api/operations/domains/{domain}` | Domain detail with metrics/signals/incidents/evidence/correlations |
| `GET` | `/api/operations/signals` | Signals, optionally filtered by domain/context |
| `GET` | `/api/operations/signals/{id}` | One signal |
| `POST` | `/api/operations/signals/{id}/investigate` | Open/create a Phase 5 investigation; no action execution |
| `GET` | `/api/operations/correlations` | Related-signal relationships |
| `GET` | `/api/operations/priorities` | Explainable priority queue |
| `GET` | `/api/operations/business-impact` | Deterministic business impact |
| `GET` | `/api/operations/health` | Source availability and configured-domain status |

Examples:

```text
GET /api/operations/snapshot
# No selected source: connected domains are NOT_CONFIGURED.

GET /api/operations/snapshot?scenario_id=payment-failure
# Controlled ShopFlow demonstration with visible simulator provenance.

GET /api/operations/domains/REVENUE?scenario_id=payment-failure
# Revenue metrics, payment signal, impact, provenance, and related correlations.
```

`POST /api/operations/signals/{id}/investigate` creates a bounded incident record only when a simulator signal does not already have an incident, then calls `InvestigationService.start()`. It never calls a tool or action executor. A later handoff calls the existing Phase 4 `AgentOrchestrator` through Phase 5; approval, risk policy, controlled action, verification, and resolution remain outside Operations.

## Frontend

- `/command-center` shows the enterprise snapshot, domain health, critical signals, impact, correlations, and deterministic priority queue alongside central orchestrator posture.
- `/operations` is the high-density operations dashboard. It supports a manual source/scenario selector and refresh; it does not poll in a background loop.
- `/operations/{domain}` provides domain detail, metrics, signals, related records/evidence, impact, correlations, and an Investigate control linking into Phase 5.

The frontend renders source labels and explicit empty/not-configured states. It never executes operational actions directly and never presents simulator numbers as real enterprise or financial information.

## Integrated ShopFlow payment demonstration

With `scenario_id=payment-failure`, the server exposes:

1. degraded Payment Service and checkout errors from the existing ShopFlow fixture;
2. deployment/configuration/log/metric evidence in IT Operations;
3. failed/successful transaction metrics and bounded USD exposure in Revenue;
4. synthetic checkout support tickets and affected-customer estimate;
5. deterministic IT → Revenue, Revenue → Support, and IT → Support relationships;
6. a high/critical server-prioritized queue and business-impact explanation;
7. an Investigate control that starts Phase 5;
8. Phase 5 handoff to the Phase 4 orchestrator, with human escalation when the local orchestrator cannot proceed;
9. no resolution without existing Phase 4 successful verification.

Every simulator-derived record remains labeled `SIMULATED / CONTROLLED DEMONSTRATION`.

## Limitations

Operations snapshots and the existing incident/investigation/orchestration stores are in-memory reference persistence. There are no external production integrations, authentication/tenant authorization, durable audit sink, or real financial/support/contract/compliance feeds in Phase 6. Those absences are represented as source boundaries rather than fabricated intelligence.
