# Phase 4 central agent orchestrator

Phase 4 adds the NEXORA ONE central orchestrator without replacing the Phase 3 Nebius Token Factory and NVIDIA Nemotron service. Nemotron supplies a validated operational summary, hypotheses, evidence references, and bounded recommendations. The server remains the authority for routing, state, permissions, policy, execution, verification, and resolution.

## Workflow and state graph

The central workflow is explicit:

```text
INCIDENT_RECEIVED
  → OBSERVING
  → INVESTIGATING
  → HYPOTHESIS_GENERATED
  → VALIDATING
  → REMEDIATION_PROPOSED
  → WAITING_FOR_APPROVAL
  → EXECUTING
  → VERIFYING
  → RESOLVED
```

The graph is implemented in `backend/app/agents/state_machine.py`. It rejects arbitrary jumps and permits safe terminal outcomes (`FAILED`, `CANCELLED`, and `REQUIRES_HUMAN`) from the appropriate operational stages. `RESOLVED` is reachable only from `VERIFYING`; the orchestrator requires all configured verification checks to pass before that transition.

Each incident has one secret-free `OrchestrationContext` containing:

- current state and runtime status;
- live or `synthetic_demo_data` source classification;
- normalized evidence references and concise summaries;
- hypothesis lifecycle (`PROPOSED`, `SUPPORTED`, `REJECTED`, or `INCONCLUSIVE`);
- selected domain/specialist and deterministic priority factors;
- proposed tools, structured execution results, risk, and execution IDs;
- remediation plan, approval record, verification plan/results, transitions, errors, and activity.

Prompts, completions, private reasoning, API keys, credentials, and raw upstream bodies are not context fields.

## Specialist registry and routing

`backend/app/agents/registry.py` registers exactly eight bounded specialist modules:

1. IT Operations
2. Revenue
3. Customer Support
4. Supply Chain
5. Contracts
6. Cloud
7. Data
8. Compliance

Specialists expose capabilities and domain-specific tool boundaries. They do not own permissions or execution. `DomainRouter` uses deterministic service/title/evidence keyword signals and returns a bounded domain selection. Unknown or weak routing is escalated instead of guessed.

`PriorityPolicy` uses incident severity, evidence coverage, server-controlled risk, and validated confidence. Model-provided risk and approval flags are not authoritative.

## Investigation and hypothesis lifecycle

The orchestrator calls the existing `AIService.analyze()` boundary. It does not create a second provider or call Nebius directly. Live analysis is grounded to repository records; simulator analysis is grounded to one explicit ShopFlow scenario. The Phase 3 provider still validates response schema, selected tool metadata, and evidence/hypothesis citations.

After Nemotron returns, the orchestrator independently collects bounded read-only logs, metrics, deployments, and health checks through the tool runtime. `HypothesisEvaluator` retains only evidence citations found in the server evidence set, marks contradictions as rejected, and escalates when there is no supported hypothesis or confidence is below the safe threshold. The model cannot declare a hypothesis validated or an incident resolved.

## Tool registry and policy

`ToolDefinition` records name, input/output schema, domain, enabled state, risk, and approval requirement. `ToolRuntime` is the only execution entry point:

1. resolve the explicit registry entry;
2. apply the server-side `ToolPolicy`;
3. validate arguments with a concrete Pydantic input model (`extra="forbid"`);
4. call the bounded simulator handler;
5. return `ToolExecutionResult` with status, structured result, evidence, timestamp, risk, and execution ID.

The implementation contains no shell, subprocess, `shell=True`, arbitrary Python, `eval`, `exec`, dynamic command path, or model-generated command execution. Read-only tools may run automatically. Low-risk tools are limited to the explicit server allow-list. Medium/high-risk tools require a pending approval that is still valid, approved, and covers the server-defined risk.

The only state-changing simulator actions are:

- `restart_payment_service`;
- `rollback_simulated_deployment`.

They mutate only an in-memory ShopFlow fixture, return `production_change: false`, and never touch production systems. Repeated approval/action requests use approval and execution identifiers; duplicate simulator action keys are rejected.

## Approval, recovery, and verification

A proposed change creates a time-limited `ApprovalRecord` and moves the incident to `WAITING_FOR_APPROVAL`. The UI can request approve/reject operations, but the backend owns the decision and policy gate. Rejection, expiration, unavailable tools, insufficient/conflicting evidence, excessive risk, and failed execution/verification end in `REQUIRES_HUMAN` or `FAILED` without resolution.

Approval execution moves through `EXECUTING` and `VERIFYING`. The simulator runs service health, bounded metrics/log reads, and `verify_resolution`. Historical evidence remains in the context; the simulated state records a clearly labelled recovery. A report is created only after verification succeeds and the state moves to `RESOLVED`.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/orchestrator/overview` | Command Center runtime and specialist overview |
| `GET` | `/api/orchestrator/agents` | Eight registered specialist runtime records |
| `GET` | `/api/orchestrator/tools` | Server allow-listed tool metadata |
| `POST` | `/api/orchestrator/incidents/{id}/start` | Start one live or explicit synthetic orchestration |
| `GET` | `/api/orchestrator/incidents/{id}` | Full orchestration context |
| `GET` | `/api/orchestrator/incidents/{id}/activity` | Orchestrator activity and audit timeline |
| `GET` | `/api/orchestrator/incidents/{id}/hypotheses` | Hypothesis lifecycle records |
| `POST` | `/api/orchestrator/incidents/{id}/cancel` | Cancel an active workflow without executing a tool |
| `GET` | `/api/orchestrator/approvals` | Approval requests, optionally filtered by status |
| `POST` | `/api/orchestrator/approvals/{id}/approve` | Server-side approval and controlled execution |
| `POST` | `/api/orchestrator/approvals/{id}/reject` | Reject and escalate without execution |
| `GET` | `/api/orchestrator/actions` | Recorded controlled action executions |
| `GET` | `/api/orchestrator/verifications` | Recorded verification results |

The reference persistence adapter is in-memory, so process restart clears orchestration runtime records. Durable persistence, authentication, role-based authorization, and a tamper-resistant audit sink remain Phase 5/production hardening work.

## Frontend integration

The existing Command Center remains the primary surface. Phase 4 extends it with server-owned orchestrator posture, real agent status, operations posture, verification/action registers, and an incident/investigation orchestration panel. The panel makes the source explicit (`live incident record` or `ShopFlow · synthetic demo`), shows approval details, and never assumes success when the backend is unavailable.

The frontend uses relative `/api` paths and never contains the Nebius credential. It may render an approval decision control, but the backend rejects unapproved high-risk actions and only the backend can transition an incident to `RESOLVED`.

## Phase 5 integration

Phase 5 adds the separate investigation/evidence-intelligence layer documented in [investigation.md](investigation.md). It collects only the existing bounded read-only probes, normalizes provenance, correlates without claiming causation, scores hypotheses server-side, and hands a supported context back through `AgentOrchestrator.start()`. The orchestrator remains the only owner of risk policy, approval, controlled actions, verification, and resolution. Durable orchestration/investigation snapshots, authenticated operator identity, richer evidence adapters, post-incident learning, and independent verification services remain future hardening work; none may weaken the model-as-untrusted-planner, fixed-action, server-policy, and verified-resolution boundaries.
