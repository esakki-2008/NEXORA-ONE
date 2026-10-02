# Phase 7 controlled autonomous actions

Phase 7 adds a single, server-owned action plane for **controlled ShopFlow demonstrations**. It does not connect to production infrastructure and it does not introduce a second tool engine. The existing Phase 4 orchestrator, Phase 5 investigation/evidence layer, Phase 4 approval/policy boundaries, verification contracts, and `ShopFlowSimulationRuntime` remain the system of record.

## Safety position

The action plane is deliberately narrower than an autonomous production operator:

- AI and investigation output may suggest a structured action or provide evidence references, but they cannot approve, authorize, calculate risk, alter a fingerprint, execute, or resolve an incident.
- The registry in `backend/app/actions/registry.py` is the only executable action source. No request can provide a callable, command, shell string, module path, dynamic import, or arbitrary tool name.
- Every mutation is deterministic in-memory `ShopFlowState` and is labeled `SIMULATED / CONTROLLED DEMONSTRATION`. A successful response includes `production_change: false`.
- Risk, normalized parameters, rollback metadata, verification strategy, fingerprint, approval expiry, and incident binding are calculated or checked on the server.
- `HIGH` risk always requires an explicit human decision and cannot use auto-execution. `MEDIUM` requires explicit approval. `READ_ONLY` remains a policy category but is not one of the seven mutating actions.
- Execution is bounded to two attempts with a five-second per-attempt timeout. Verification failure invokes the registered rollback path; failure to verify rollback escalates to `REQUIRES_HUMAN`.
- An incident becomes resolved only after controlled execution and server verification pass. Rejection, timeout, failed verification, or rollback leaves the incident for human review.

This boundary is intentionally not a production authorization system. Operator identity is an auditable field in this local reference implementation; authenticated identity, tenant authorization, and durable storage are outside Phase 7.

## Allow-listed actions

The registry exposes exactly these seven names:

| Action | Risk | Parameters | Expected impact |
| --- | --- | --- | --- |
| `restart_payment_service` | `MEDIUM` | `{}` | Restore simulated Payment Service health and reduce payment failures |
| `rollback_simulated_deployment` | `HIGH` | `deployment_id` | Return one named simulated deployment to its previous state |
| `restart_checkout_service` | `MEDIUM` | `{}` | Restore simulated Checkout Service health and relevant latency/error posture |
| `clear_simulated_queue` | `HIGH` | `queue_name` | Set one allow-listed synthetic queue depth to zero |
| `disable_simulated_feature_flag` | `MEDIUM` | `feature_name` | Disable one allow-listed feature flag |
| `restore_simulated_configuration` | `MEDIUM` | `configuration_id` | Restore one known-good synthetic configuration value |
| `scale_simulated_service` | `HIGH` | `service_name`, `desired_capacity` from 1 to 100 | Change only a bounded in-memory capacity value |

Each parameter model uses `extra="forbid"` and strict field types. Queue, feature, configuration, service, deployment identifier, and capacity values are bounded; malformed, unknown, or malicious values fail before runtime dispatch.

## Lifecycle

An action is an immutable proposal plus append-oriented lifecycle state:

```text
PENDING_APPROVAL
      │
      ├── approve ──> APPROVED ── execute ──> EXECUTING
      │                                      │
      │                                      ├── verification pass ──> COMPLETED
      │                                      ├── verification fail + rollback pass ──> ROLLED_BACK
      │                                      └── bounded failure/rollback failure ──> REQUIRES_HUMAN
      ├── reject ──> REJECTED
      ├── cancel ──> CANCELLED
      └── approval expiry ──> EXPIRED
```

Creation computes a canonical SHA-256 fingerprint over the incident ID, normalized parameters, registered action name, server risk, impact, and rollback plan. The action ID, idempotency key, approval record, and audit reference are all retained. Approval is bound to the same action ID, incident ID, and fingerprint. The service revalidates the fingerprint before approval and execution; changing an approved action is a conflict, not a new permission.

The append-only audit trail is hash chained per action. `GET /audit` verifies the chain before returning events. Audit metadata contains safe structured references only; it does not contain prompts, model completions, credentials, shell commands, or raw provider responses.

## Investigation and orchestrator integration

The intended ShopFlow payment-failure flow is:

1. Incident intake creates the Payment Service incident.
2. Operations or the existing investigation surface selects `payment-failure` and gathers simulator evidence.
3. Phase 5 produces provenance-preserving evidence, deterministic correlations, hypotheses, and a guarded handoff to the existing Phase 4 orchestrator.
4. The Phase 7 planner consumes the incident and optional investigation/orchestration context. It selects a fixed registry entry and derives missing parameters server-side.
5. A human reviews the exact action detail, risk, impact, rollback conditions, verification strategy, parameters, incident binding, and fingerprint.
6. A distinct authorized human approves. Approval never executes automatically.
7. The action executor invokes only the registered simulator handler with bounded timeout/retry behavior.
8. The existing verification boundary plus the simulator verification adapter checks the expected state.
9. Only a passed verification can resolve the incident and create the report. Rollback or failure adds a human escalation and preserves the audit timeline.

Operations can link to the action surface but cannot execute an action directly. The browser never calls the simulator or a privileged executor; it calls the action API, and the backend owns policy and lifecycle transitions.

## API routes

All routes are under `/api/actions`:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/registry` | Return safe metadata and JSON schemas for the seven registered actions; no callables |
| `GET` | `/` | List actions, optionally filtered by `?status=` |
| `POST` | `/` | Create a validated, incident-bound proposal |
| `GET` | `/{action_id}` | Retrieve one action record |
| `POST` | `/{action_id}/approve` | Approve the exact pending fingerprint as an authorized human |
| `POST` | `/{action_id}/reject` | Reject and escalate the action |
| `POST` | `/{action_id}/execute` | Execute an approved registered action; `auto_execute` cannot bypass high risk |
| `POST` | `/{action_id}/cancel` | Cancel before execution |
| `POST` | `/{action_id}/rollback` | Restore captured before-state after an eligible execution |
| `GET` | `/{action_id}/audit` | Return and integrity-check the hash-chained events |
| `GET` | `/{action_id}/verification` | Return verification status, strategy, before/after state, and rollback status |

A create request contains `incident_id`, an explicit or context-derived `scenario_id`, optional `investigation_id`, an allow-listed `action_name` or bounded recommendation, parameters, and an idempotency key. It does not contain risk, approval status, execution state, fingerprint, rollback authority, or verification state; those fields are not client-controlled.

Example proposal:

```json
{
  "incident_id": "<incident UUID>",
  "scenario_id": "payment-failure",
  "action_name": "restart_payment_service",
  "parameters": {},
  "requested_by": "phase7-planner",
  "idempotency_key": "payment-demo-restart-1"
}
```

Example human approval and execution requests:

```json
{
  "requested_by": "Local operator",
  "reason": "Reviewed the incident evidence and exact simulator fingerprint.",
  "auto_execute": false
}
```

Unknown actions, extra parameters, missing simulator binding, wrong incident/investigation binding, unauthorized actors, rejected/expired approvals, changed fingerprints, and duplicate executions return safe validation or conflict responses. They do not reach the simulator.

## Frontend surfaces

- `/remediation` is the **Controlled Actions** register. It shows the simulator boundary, seven-action registry, proposal form, approval queue, risk posture, and action ledger.
- `/remediation/{actionId}` is **Action Detail**. It presents the exact normalized parameters, impact, rollback plan, verification contract, SHA-256 fingerprint, approval controls, hash-chained audit events, and before/after verification record.
- Incident Detail, Operations, and Command Center link to the controlled action surface without granting an implicit approval.
- The UI renders server state after each mutation. It never marks an action approved, executed, verified, rolled back, or resolved locally.

## Validation expectations

Run the repository checks before treating the Phase 7 boundary as complete:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check backend
.venv/bin/mypy backend/app
cd frontend && npm ci && npm run test -- --run && npm run typecheck && npm run build
```

The action tests cover unknown actions, malformed parameters, missing/wrong bindings, AI and unauthorized actor rejection, high-risk auto-execution rejection, idempotent proposals/execution, changed fingerprints, approval rejection/cancellation, successful payment recovery, verification/report integration, and explicit rollback.
