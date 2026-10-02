# NEXORA ONE architecture

Phase 7 preserves the Phase 1 foundation, Phase 2 Command Center, Phase 3 server-only Nebius/NVIDIA inference boundary, Phase 4 stateful policy-controlled central orchestrator, Phase 5 investigation/evidence-intelligence layer, and Phase 6 unified enterprise operations intelligence boundary while adding one controlled autonomous-action plane for deterministic ShopFlow demonstrations.

## Design goals

1. Keep domain models independent from HTTP, model vendors, and storage engines.
2. Make every agent, tool, action, and verification step explicit and auditable.
3. Prefer a bounded failure over fabricated AI output or an unapproved action.
4. Make Phase 3 provider integration and Phase 4 orchestration additive rather than a rewrite.

## Backend boundaries

```text
backend/app/
├── api/            FastAPI routes and dependency wiring
├── agents/         agent contracts, registry, orchestrator boundary, state graph
├── ai/             Nebius/Nemotron provider, validated schemas, service, and lifecycle events
├── config/         environment-backed settings
├── database/       repository port and Phase 1 in-memory adapter
├── models/         canonical domain records and enums
├── schemas/        HTTP input/output models
├── services/       application use cases
├── simulator/      structured ShopFlow fixtures
├── tools/          allow-listed tool definitions and registry
├── verification/   verification request/result contract
├── investigation/  Phase 5 context, collection, normalization, correlation, scoring, and handoff
├── operations/     Phase 6 unified domain health, signals, metrics, impact, priorities, and snapshots
└── actions/        Phase 7 registry, planner, policy, approval, executor, rollback, audit, and service
```

### API and services

Routes validate HTTP data using Pydantic and delegate to `IncidentService`. The service owns incident creation and looks up nested resources through `IncidentRepository`. Routes do not know whether storage is in memory or PostgreSQL.

### Database boundary

`IncidentRepository` is a protocol. `InMemoryIncidentRepository` is the Phase 1 reference adapter, designed for deterministic tests and a zero-dependency local start. A later PostgreSQL adapter can implement the same operations using the configured `DATABASE_URL`; consumers do not need to change.

### AI boundary

The required path is:

```text
Frontend → FastAPI NEXORA Backend → AIService → Nebius Token Factory → NVIDIA Nemotron
                                                                  ↓
                                         validated AIAnalysisResponse → Command Center
```

`AIRequest` is the provider-neutral input contract. `NebiusNemotronProvider` is the only Phase 3 provider and uses the Nebius OpenAI-compatible chat-completions endpoint through `httpx`. It receives `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `NEBIUS_TIMEOUT_SECONDS`, and `NEBIUS_MAX_RETRIES` from server settings. The key is held as `SecretStr` and is not part of an `AIHealthResponse`, `AIActivityEvent`, exception message, or frontend contract.

`AIService` is the application boundary. It normalizes one live incident or one read-only ShopFlow fixture, marks fixtures as `synthetic_demo_data`, builds a constrained prompt with the response schema and future tool catalog, invokes the provider, and consumes only the already-validated `AIAnalysisResponse`. There is no provider fallback and no fabricated output when configuration or connectivity is missing.

The provider requests JSON mode, handles authentication/model/provider/timeout/retry failures without returning upstream bodies, parses the OpenAI-compatible envelope, and validates the model content with Pydantic. The response envelope contains status, current step, summary, selected tool proposals, evidence, hypotheses, validated hypothesis, recommendation, risk, approval requirement, verification plan, and confidence. Evidence references are checked against an NEXORA-supplied evidence index and trusted source/summary fields are copied from that index, so the model cannot add fabricated evidence. Selected tools must belong to `FOUNDATION_TOOL_CATALOG` and match its risk metadata; they remain proposals and are never executed in Phase 3.

`GET /api/ai/health` reports configuration and the last real verification state. `POST /api/ai/test` performs a real structured request, so `verified` becomes true only after a successful provider response passes validation. `POST /api/ai/analyze` is evidence-bound. `GET /api/ai/activity` returns concise lifecycle events only—no prompt, completion, chain-of-thought, or credential.

### Agent boundary

`SpecialistAgent` is an abstract contract. `AgentDirectory` is an explicit registry containing eight bounded domain modules. `AgentOrchestrator` owns routing, priorities, evidence validation, policy, approval, execution, verification, and escalation. `AgentStateMachine` enforces the lifecycle:

```text
IDLE → INCIDENT_RECEIVED → OBSERVING → INVESTIGATING
     → HYPOTHESIS_GENERATED → VALIDATING → REMEDIATION_PROPOSED
     → WAITING_FOR_APPROVAL → EXECUTING → VERIFYING → RESOLVED
```

`FAILED`, `CANCELLED`, and `REQUIRES_HUMAN` are explicit safe outcomes. No implicit retry, approval bypass, or resume behavior is allowed. See [orchestrator.md](orchestrator.md) for the Phase 4 context, policy, simulator, and API details.

### Tool boundary

Tool definitions carry input/output schemas, domain, enabled state, risk, and approval requirements. `ToolRuntime` validates every call and applies server policy before a concrete `ControlledTool` receives data. The registry has no API for arbitrary shell commands, subprocesses, eval, or dynamic imports. Phase 4 execution is limited to read-only ShopFlow evidence and the fixed `restart_payment_service` / `rollback_simulated_deployment` simulator actions.

### Investigation boundary

Phase 5 is a separate application layer under `backend/app/investigation/`:

```text
InvestigationService
        │
InvestigationEngine ── InvestigationStore
   │       │      │       │
   │       │      │       └── secret-free context/idempotency indexes
   │       │      └── HypothesisEngine + HypothesisScorer
   │       └── EvidenceNormalizer + EvidenceCorrelator
   └── existing ToolRuntime / ToolPolicy / ShopFlow runtime
```

`InvestigationContext` is the aggregate returned to the API and frontend. `EvidenceNormalizer` converts existing `ToolExecutionResult` records into bounded provenance records. `EvidenceCorrelator` applies deterministic, non-causal relationship rules. `HypothesisEngine` creates bounded scenario-specific candidates; `HypothesisScorer` computes server-owned confidence and factor explanations. `InvestigationTimeline` records collection, analysis, testing, failure, and handoff events.

The engine can call only Phase 4 read-only tools and the bounded `run_test` probe. It generates tool arguments server-side, validates citations against server evidence, and persists legacy-compatible evidence/hypothesis/activity records through `IncidentRepository`. The optional `AIService` is assistive: validated Nemotron output can add a candidate or summary, but AI cannot execute, approve, mutate state, set authoritative confidence, or resolve an incident.

The store indexes incident and request IDs to make starts idempotent. A supported result is handed to `AgentOrchestrator.start()`; investigation never calls an action executor or bypasses Phase 4 approval, risk, controlled-action, or verification boundaries. A live incident without evidence, unavailable collection, invalid AI, conflicting evidence, or low support escalates safely.

### Operations boundary

Phase 6 is a read/intelligence layer under `backend/app/operations/`. It has one `OperationsService` and one snapshot assembly path; domain endpoints do not contain duplicate calculations:

```text
OperationsService
   │
   ├── source-aware snapshot assembly
   ├── DomainHealth + ServiceHealth + BusinessMetric
   ├── OperationalSignal + domain-specific signal contracts
   ├── CrossDomainCorrelation (related signals, never causation)
   ├── BusinessImpact (bounded deterministic estimate)
   └── PriorityItem (server-owned explainable factors)
```

`OperationsDomain` represents IT, Revenue, Support, Supply Chain, Contracts, Cloud, Data, and Compliance. `SourceMetadata` is attached to every record. The service returns `NOT_CONFIGURED` when a source is absent and only adds controlled simulator records when an explicit `scenario_id` is selected. The default snapshot therefore cannot manufacture health, financial, customer, contract, or compliance values.

The Phase 6 service reads active incident and repository evidence through `IncidentRepository`, reads ShopFlow through the existing `ShopFlowSimulationRuntime`, and opens investigations through the existing `InvestigationService`. It never calls `ToolRuntime` directly for remediation. Operations → Investigation → Orchestrator remains the only transition; Phase 4 still owns risk policy, approval, controlled actions, verification, and resolution.

`POST /api/operations/signals/{id}/investigate` is a bounded context-creation request. It may create a clearly simulator-labeled incident for a selected simulator signal, then starts Phase 5. It cannot execute a tool, approve a plan, mutate production state, or mark a record resolved.

### Controlled action boundary

Phase 7 is one application service under `backend/app/actions/`; it does not replace the Phase 4 tool runtime or create a parallel orchestrator:

```text
ActionService
   │
   ├── ActionPlanner ── ActionRegistry (seven fixed definitions)
   ├── ActionPolicy ── ApprovalService (existing ApprovalRecord)
   ├── ActionExecutor ── VerificationRunner
   ├── RollbackPolicy ── ShopFlowSimulationRuntime
   ├── ActionIdempotencyStore
   └── AuditTrail (append-only hash chain)
```

`ActionRegistry` is the only executable source. Its definitions bind strict Pydantic parameter models, server-owned risk, expected impact, rollback conditions, verification strategy, and a constant runtime handler name. `ActionPlanner` consumes incident, investigation, and orchestration context but stores only structured summaries and evidence identifiers. `ActionService` validates the incident/investigation binding, calculates the canonical fingerprint, reuses the Phase 4 `ApprovalRecord`, applies actor/risk/expiry policy, and owns all lifecycle transitions.

`ActionExecutor` invokes only a validated registry handler with bounded attempts and timeouts. The handler mutates only deterministic in-memory ShopFlow simulator state and returns before/after state plus a verification target. Verification is structured and server-owned. A failed verification uses the captured before-state through the registered restore path; rollback verification or human escalation is recorded before any incident status change. A passed verification is the sole path that creates the controlled-action report and resolves an incident.

The action service is intentionally separate from the existing Phase 4 two-action tool boundary while reusing its orchestrator, investigation, approval, policy, simulator, and verification infrastructure. The two registries are not interchangeable: Phase 4 read/tools remain available for investigation, and Phase 7 action names remain the only Phase 7 executables.

### Verification boundary

`VerificationRunner` accepts a structured `VerificationRequest` and returns a structured `VerificationResult`. This prevents an action from being considered successful merely because an invocation returned without an error. Phase 7 adds simulator-specific state verification behind that same structured boundary.

## Frontend boundaries

The frontend is a Vite single-page app:

- `api/` contains relative-path API clients;
- `components/` contains the shell, icon set, tables, health cards, timelines, status, and loading/error/empty primitives;
- `hooks/` contains request lifecycle state with timeout/error/retry behavior;
- `lib/` contains display formatting and domain-source mapping only;
- `pages/` contains route-level command center, monitor, intelligence, action, reporting, and system surfaces;
- `types.ts` mirrors only public response contracts and simulator records.

Phase 2 uses real incident, activity, evidence, hypothesis, report, health, and simulator endpoints. Phase 3 extends the UI with backend-sourced AI health and lifecycle activity. Phase 4 adds server-owned orchestration posture, specialist status, approval details, action records, verification records, and incident/investigation controls. Phase 5 adds evidence provenance, simulator classification, correlations, deterministic confidence factors, hypothesis lifecycle/gaps, root-cause candidates, next-step guidance, timeline events, and an approval-preserving handoff control. Phase 6 adds the unified Operations snapshot, eight-domain health, source status, signals, metrics, cross-domain correlations, business impact, priorities, and `/operations/{domain}` detail. Phase 7 adds `/remediation` Controlled Actions and `/remediation/{actionId}` Action Detail, including the registry boundary, proposal intake, fingerprint review, human approval controls, rollback, verification, and audit history. When a source is absent, the UI says so instead of manufacturing a score, provider connection, recommendation, activity, or resolution. Simulator observations carry a visible synthetic/demo label and do not become live incident records.

In development, Vite proxies `/health` and `/api` to the backend. Browser code never calls localhost directly; it calls relative paths so the same build works behind a preview host or reverse proxy.

## Extension path

- Phase 2 can add dashboard query services without changing incident records.
- Phase 3 now provides the real Nebius/Nemotron adapter, validated response contract, health/test/analyze/activity routes, and mocked provider tests.
- Phase 4 now registers specialist agents, orchestrator policies, approval APIs, simulator execution, verification, escalation, and report generation.
- Phase 5 now adds a dedicated investigation context, bounded collection/normalization/correlation, server-scored hypotheses, provenance, gaps, timeline, and orchestrator handoff.
- Future phases can add durable investigation/orchestration snapshots, authenticated operator identity, richer evidence adapters, and post-incident learning without weakening server policy.
- Phase 6 can add domain-specific repositories and tools without duplicating the snapshot boundary.
- Phase 7 is implemented here as the fixed, simulator-only controlled action plane documented in [actions.md](actions.md).
