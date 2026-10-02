# Phase 8 — Verification & Reliability Engine

Phase 8 extends the existing Phase 7 verification boundary. It does not create a second action executor, simulator, policy engine, or resolution path. The flow is:

```text
registered action
  → approved bounded execution
  → Phase 8 verification record
  → allow-listed read-only collection
  → expected versus actual comparisons
  → confidence factors and provenance evidence
  → passed proof OR bounded recovery/rollback OR human escalation
  → resolution gate
```

The ShopFlow implementation is explicitly `SIMULATED / CONTROLLED DEMONSTRATION`. It proves only the in-memory fixture state; it does not claim to verify production infrastructure.

## Server-owned record

`Verification` is a strongly typed, integrity-checked record with:

- `verification_id`, `incident_id`, `action_id`, and the exact action fingerprint;
- lifecycle state: `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `INCONCLUSIVE`, `RETRYING`, `RECOVERY_REQUIRED`, `REQUIRES_HUMAN`, or `CANCELLED`;
- start/completion/audit timestamps, bounded `attempt` and `max_attempts`;
- server-calculated `expected_state`, read-only `actual_state`, checks, evidence IDs, confidence, structured confidence factors, failure reason, recovery metadata, escalation metadata, execution result, and an integrity hash.

The client can submit only an action identity or operator context. It cannot submit expected state, actual state, status, risk, policy, approval, evidence trust, confidence, or resolution state.

## Deterministic strategies

The engine builds checks from the registered action and the bound simulator state. The available strategies are:

- `SERVICE_HEALTH`
- `ERROR_RATE`
- `LATENCY`
- `DEPLOYMENT_STATE`
- `CONFIGURATION_STATE`
- `QUEUE_STATE`
- `FEATURE_FLAG_STATE`
- `CAPACITY_STATE`
- `TRANSACTION_SUCCESS` for the existing payment recovery boundary

A check is included only when its read-only value is legitimately available. For example, a latency fixture without an error-rate metric does not receive a fabricated error-rate check. Multiple independent checks are required where the simulator provides them.

## Collection, comparisons, and evidence

`SimulatorVerificationCollector` is the only Phase 8 collector in the local application. It reads through the existing `ShopFlowSimulationRuntime` and the already allow-listed read-only `ToolRuntime`. It does not accept tool names, commands, callables, filesystem paths, or state from the browser.

Every check records its expected value, actual value, comparison, status, trust label, observation timestamp, and evidence IDs. Evidence uses one of:

- `TRUSTED` — an explicitly trusted connected source;
- `SIMULATED` — the ShopFlow controlled demonstration boundary;
- `UNTRUSTED` — present but not acceptable as proof;
- `UNAVAILABLE` — the source did not provide a value.

Evidence includes source, collector, timestamp, scenario/action/incident provenance, controlled-demonstration labels, and a stable evidence ID. Phase 8 evidence is also copied into the existing incident evidence ledger after an action, so investigation, incident detail, and reports can use the same evidence boundary.

## Confidence

Confidence is a deterministic bounded score from explicit factors: health, error rate, latency, expected-state match, independent-check count, freshness, contradiction, missing evidence, and required-check pass rate. It does not consume model text, hidden reasoning, or a client-provided number. Simulated evidence remains labeled simulated even when it proves a simulator state.

A stale, contradictory, unavailable, or untrusted check cannot open the resolution gate. Evidence freshness defaults to five minutes and is configurable through `VERIFICATION_MAX_EVIDENCE_AGE_SECONDS`.

## Lifecycle and retries

The service owns all transitions and rejects transitions not in the allow-list. Running verification is serialized per record; duplicate action bindings return the existing record, and concurrent runs are rejected rather than racing. Attempts are bounded to one through three (`VERIFICATION_MAX_ATTEMPTS`, default three). Explicit retry calls use deterministic exponential backoff based on `VERIFICATION_RETRY_DELAY_SECONDS` and never start an unbounded loop.

Cancellation is safe only before a terminal proof and does not turn an incomplete action into a pass. A cancelled action cannot be verified later. Historical records, evidence, and timeline events are immutable at the store boundary; verification records and timeline events carry SHA-256 integrity links.

## Recovery and resolution gate

A failed or inconclusive result selects at most one existing registry action as a recovery recommendation. The policy never invents a command or recovery name. Recovery remains approval-gated and no automatic retry loop is created. Existing Phase 7 rollback is verified against the exact captured before-state. If recovery or rollback cannot be proven, the action and incident remain `REQUIRES_HUMAN` and Operations marks the affected posture degraded.

Execution success alone never resolves an incident. `ActionService._resolve_incident` requires all of the following:

1. a matching verification record;
2. matching incident ID, action ID, and action fingerprint;
3. `PASSED` status;
4. every required check passed with acceptable trust;
5. fresh, non-contradictory, available evidence;
6. an intact record and timeline integrity boundary.

Only then are the incident, activity timeline, report, and resolution audit event updated.

## API

All endpoints are under `/api/verification`:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/verification` | List records; filter by `status`, `incident_id`, or `action_id` |
| `GET` | `/api/verification/summary` | Return bounded reliability metrics |
| `POST` | `/api/verification` | Create a record from a server-known action ID |
| `GET` | `/api/verification/{id}` | Retrieve one integrity-checked record |
| `POST` | `/api/verification/{id}/run` | Run one server-owned attempt |
| `POST` | `/api/verification/{id}/retry` | Run the next bounded attempt |
| `POST` | `/api/verification/{id}/cancel` | Cancel a safe non-terminal record |
| `GET` | `/api/verification/{id}/evidence` | Retrieve provenance-aware evidence |
| `GET` | `/api/verification/{id}/timeline` | Retrieve the hash-chained activity timeline |

The create/run/retry/cancel request bodies contain only an operator identity and optional reason. No state, expected value, confidence, trust, risk, policy, authorization, action body, or resolution field is accepted.

## UI integration

- `/verification` shows the Phase 8 register, summary, action bindings, bounded statuses, and explicit simulator labeling.
- `/verification/:id` shows expected/actual state, individual comparisons, trust labels, confidence factors, evidence, recovery/cancellation controls, and timeline hashes.
- Command Center shows proof counts and human-review posture.
- Operations keeps human-escalated incidents degraded and links to verification review.
- Incident detail shows verification history and keeps the resolution gate visible.
- Action detail links execution to the richer verification record.

## Tests and limitations

Deterministic coverage includes normal payment recovery, forced verification failure and rollback, retry behavior, permanent failure, contradictory/unavailable/stale evidence, cancellation, forged state/confidence/fingerprint attempts, wrong-incident bindings, duplicate/concurrent runs, modified records, invalid transitions, and unknown recovery targets.

The reference store remains in-memory, as in earlier phases. It is suitable for the controlled demonstration and tests but is not durable production storage. Phase 8 ends here; production hardening and later roadmap phases are intentionally out of scope.

## Phase 9 security hardening

Verification is a tenant-bound server proof, not a client status field:

- `/api/verification*` requires an authenticated principal and the route's explicit RBAC permission;
- create/run/retry/cancel actor values are bound to the authenticated subject; omitted create/run/retry identity is filled by the server where supported;
- verification records are scoped to the principal tenant and exact action/incident/fingerprint relationship; cross-tenant reads and mutations return safe not-found responses;
- expected state, actual state, trust labels, confidence, attempt/status, recovery, rollback, and resolution are computed by the service and cannot be submitted as authority;
- retry/cancel routes use bounded rate/retry policies and stale-state/lock checks; a cancelled or terminal record cannot be used to prove resolution;
- record integrity hashes and timeline hash links are checked before history is returned; tampered records safely return `409` and generate security telemetry;
- execution success alone remains insufficient: only a fresh, intact, complete, matching `PASSED` proof can resolve the incident or generate a resolved report.

The engine continues to read only registered simulator/read-only sources and preserves `SIMULATED / CONTROLLED DEMONSTRATION`. Phase 9 hardens the existing Phase 8 boundary without creating another verification or execution path.
