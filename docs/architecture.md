# NEXORA ONE architecture

NEXORA ONE is a controlled enterprise operations plane. Phase 1–8 provide the domain, intelligence, orchestration, action, and verification flow; Phase 9 places authentication, authorization, tenant scope, input validation, and integrity controls around those existing boundaries. Phase 10 is not started.

## System flow

```text
browser / operator / source data / AI output
                    │ untrusted input
                    ▼
        ┌───────────────────────────┐
        │ HTTP security boundary    │
        │ size → auth → RBAC → rate │
        └─────────────┬─────────────┘
                      ▼
             tenant-scoped services
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
   Incidents      AI/Investigation  Operations
       │              │              │
       └──────────────┼──────────────┘
                      ▼
              Central Orchestrator
                      │
              approval/policy gate
                      │
       registered tools/actions only
                      │
              simulator execution
                      │
          verification and recovery
                      │
         proof-gated report/resolution
```

The model is a structured, untrusted planner. It does not become an operating-system user, identity provider, policy engine, executor, verifier, or resolution authority.

## Repository and application composition

The backend uses a repository protocol so domain services do not depend on a concrete database adapter. The current `InMemoryIncidentRepository` is thread-safe and intentionally a reference implementation. A PostgreSQL-compatible adapter can replace it without changing the public contracts.

```text
backend/app/
├── api/routes/       FastAPI route adapters and HTTP error mapping
├── security/         reference auth, RBAC, tenant, validation, events, integrity
├── config/           environment-backed settings and SecretStr fields
├── database/         IncidentRepository port and in-memory adapter
├── models/           incident/action/evidence/report domain models
├── schemas/          incident and activity request/response contracts
├── services/         incident use cases
├── ai/               Nebius/Nemotron provider and bounded inference service
├── tools/            registered read-only tool catalog/runtime
├── agents/           orchestrator, specialists, policy, state machine, stores
├── investigation/    evidence collection, normalization, correlation, hypotheses
├── operations/       unified eight-domain source-aware intelligence
├── actions/          seven-name controlled action plane and audit
├── verification/    proof, recovery, timeline, integrity, resolution gate
└── simulator/        ShopFlow controlled demonstration fixture/runtime
```

`main.create_app()` wires the services once, injects the shared security service into AI/tool/runtime boundaries, and registers routes. Route dependencies obtain only server-owned service objects from application state.

## Public domain contracts

Pydantic models use strict/ bounded fields, explicit enums, and `extra="forbid"` where request authority could otherwise be smuggled through unknown fields. Domain models carry `tenant_id` and relationship IDs. The browser receives public records, never callables, handler names, private prompts, API credentials, or unrestricted simulator objects.

The core lifecycle is:

```text
Incident
  → evidence and activity
  → InvestigationContext / hypotheses / correlations
  → OrchestrationContext / specialists / plan
  → ApprovalRecord
  → registered action or read-only tool
  → Verification
  → IncidentReport only after proof
```

## Phase 3 AI boundary

```text
AIService
   ├── source normalization (live incident or synthetic scenario)
   ├── untrusted-data delimiters and prompt-injection observation
   ├── bounded AIRequest construction
   ├── NebiusNemotronProvider (OpenAI-compatible JSON request)
   ├── AIAnalysisResponse schema validation
   ├── evidence-index/tool/action/tenant/incident validation
   └── tenant-scoped lifecycle events
```

`NebiusNemotronProvider` is the only provider implementation. It reads `NEBIUS_API_KEY`, `NEBIUS_MODEL`, and `NEBIUS_BASE_URL` server-side, uses bounded timeout/retries, requests JSON mode, and converts failures to safe typed errors. `AIService` validates both analysis and connectivity-test output. Synthetic input is labeled `synthetic_demo_data`; ShopFlow public responses retain `SIMULATED / CONTROLLED DEMONSTRATION`.

The service never executes model-selected tools. Every evidence citation must be in a server-generated evidence index. Every selected tool must be in `FOUNDATION_TOOL_CATALOG`, match its registered risk, pass `validate_tool_input`, and obey resource/tenant references. Nested action proposals are checked with `validate_public_action()` and still require the existing action service/approval path.

## Phase 4 orchestrator and tool boundary

```text
AgentOrchestrator
   ├── AgentStateMachine
   ├── DomainRouter / PriorityPolicy / HypothesisEvaluator
   ├── eight registered specialist modules
   ├── ToolPolicy
   ├── ToolRegistry → ToolRuntime → ShopFlowSimulationRuntime
   ├── ApprovalRecord
   └── verification/report handoff
```

The orchestrator owns one state machine per incident and uses deterministic policy for routing, prioritization, hypothesis lifecycle, approval, execution, verification, escalation, and reporting. The `ToolRegistry` contains only explicit `ControlledTool` instances. `ToolRuntime` validates arguments before handlers and returns structured status/evidence. It has no arbitrary command, shell, subprocess, dynamic import, filesystem, `eval`, or `exec` boundary.

The AI/orchestrator call accepts a tenant keyword so live and synthetic inference activity cannot fall back to a global reference tenant. The orchestrator receives structured AI facts, not private reasoning or authority.

## Phase 5 investigation boundary

```text
InvestigationService
        │
InvestigationEngine ── InvestigationStore
   │       │       │       │
   │       │       │       └── tenant/request/incident idempotency
   │       │       └── HypothesisEngine + HypothesisScorer
   │       └── EvidenceNormalizer + EvidenceCorrelator
   └── existing read-only ToolRuntime / ToolPolicy / ShopFlow runtime
```

`InvestigationContext` is the aggregate returned to the API. The normalizer preserves collector, source, raw reference, timestamp, confidence/relevance, collection status, tenant, and simulator label. Correlations are deterministic and non-causal. Hypothesis status and confidence factors are server-owned. AI can add only validated candidate data; it cannot approve, execute, mutate tenant/risk/policy, or resolve.

The store indexes incident/request IDs for idempotent starts and deduplicates evidence. Investigation routes pass tenant scope through start, collect, test, handoff, and cancel. Cancellation also binds the requested actor to the authenticated principal.

## Phase 6 operations boundary

```text
OperationsService
   ├── source-aware snapshot assembly
   ├── DomainHealth / ServiceHealth / BusinessMetric
   ├── OperationalSignal and domain-specific records
   ├── CrossDomainCorrelation (related signals, never causation)
   ├── BusinessImpact (bounded deterministic estimate)
   └── PriorityItem (server-owned explainable factors)
```

The eight domains are IT, Revenue, Support, Supply Chain, Contracts, Cloud, Data, and Compliance. `SourceMetadata` is attached to public operations records. Missing sources return `NOT_CONFIGURED`; absence is never treated as healthy or zero. Operations can open the existing Phase 5 investigation boundary, but cannot call a mutating tool, approve a plan, execute an action, or mark an incident resolved. Optional actor fields are server-bound to the authenticated principal.

## Phase 7 controlled action boundary

Phase 7 is one application service and does not replace the Phase 4 tool runtime:

```text
ActionService
   ├── ActionPlanner → ActionRegistry (exactly seven definitions)
   ├── ActionPolicy → ApprovalService (existing ApprovalRecord)
   ├── ActionExecutor → VerificationService
   ├── RollbackPolicy → ShopFlowSimulationRuntime
   ├── ActionIdempotencyStore
   └── AuditTrail (per-action append-only hash chain)
```

`ActionRegistry` binds dedicated Pydantic parameter models, server-owned risk, expected impact, rollback conditions, verification strategy, and constant handlers. `ActionPlanner` consumes incident/investigation/orchestration context and stores structured summaries/evidence IDs only. Action fingerprints cover the exact server plan. The service checks tenant, incident, scenario, investigation, approval, actor, expiry, and stale state before mutation.

The executor has bounded attempts/timeouts and mutates only deterministic in-memory ShopFlow state. Failed verification uses the captured before-state through a registered restore path. An unverified rollback escalates. A passed verification is the sole action-service path to report-integrated incident resolution.

## Phase 8 verification boundary

```text
ActionExecutor
      │ exact action + execution result
      ▼
VerificationService ── VerificationStore (record integrity + lifecycle lock)
      │                         │
      ▼                         ├── append-only evidence/timeline
VerificationEngine              └── incident resolution proof gate
      │
      ├── expected state from ActionRegistry + simulator
      ├── SimulatorVerificationCollector
      ├── deterministic registered strategies
      ├── confidence factors/freshness/contradiction
      └── RecoveryPolicy → registered rollback boundary
```

`VerificationService` owns transitions, retries, cancellation, tenant/action/incident/fingerprint binding, integrity, evidence, timeline, recovery, and proof validation. `VerificationEngine` never accepts client state or arbitrary tool names. It reads only from `ShopFlowSimulationRuntime` and the existing read-only `ToolRuntime` boundary.

`ActionService` injects the verification service into the existing executor; execution is not mapped to a resolved incident unless a fresh, intact, complete, matching `PASSED` record is returned. Phase 8 evidence is copied into the incident ledger so reports/investigation/operations share provenance.

## Phase 9 security boundary

Phase 9 wraps the existing services rather than creating parallel use cases:

```text
Request
  │
  ├── declared + streamed request size
  ├── TokenAuthenticator → Principal(subject, tenant, roles, expiry)
  ├── SecurityPolicy.permission_for → AuthorizationService
  ├── exact actor binding and resource tenant scope
  ├── sensitive-route rate limiter
  ▼
Existing Phase 1–8 service
  │
  ├── AI: untrusted-data framing → evidence/tool/action/output validation
  ├── tools: registered catalog → strict input → bounded simulator
  ├── actions: registry → fingerprint → approval → executor
  ├── verification: proof/recovery/integrity/resolution gate
  └── tenant-scoped repository/store/audit/security events
```

### Security modules

- `authentication.py` provides the signed **REFERENCE SECURITY IMPLEMENTATION**. It is not a production identity provider; production requires an environment/secret-manager HMAC secret and eventual IdP replacement.
- `authorization.py`, `permissions.py`, and `policies.py` define explicit `VIEWER`, `OPERATOR`, `APPROVER`, and `ADMIN` permissions and endpoint/rate mappings.
- `tenant.py` validates tenant IDs; services receive the principal tenant, never a client-selected tenant.
- `validation.py` and `main.py` apply bounded identifiers, outbound HTTPS/SSRF checks, and declared/streamed body limits.
- `sanitization.py` frames untrusted data, observes prompt injection, and redacts credential-like metadata.
- `security_events.py` stores a redacted tenant-aware hash chain; `actions/audit.py` and `verification/service.py` provide corresponding integrity boundaries.

Tenant identity is propagated through AI service calls, orchestrator/investigation analysis, tool-runtime execution, action audit material, AI activity, verification, and security events. Scope is checked at routes and repeated at services/stores. Cross-tenant reads/mutations fail safely.

The HTTP middleware adds safe error mapping, security headers, explicit CORS, and bounded sensitive-route budgets. `/health` remains liveness-only. The browser uses relative URLs; Vite's loopback target is a server-side development proxy and never a browser-facing dependency.

## Frontend boundaries

The frontend is a Vite single-page app:

- `api/` contains relative-path API clients and optional runtime-injected reference bearer token;
- `components/` contains shell, tables, health cards, timelines, status, loading/error/empty primitives;
- `hooks/` contains request lifecycle timeout/error/retry state;
- `lib/` contains display formatting/domain mapping only;
- `pages/` contains command center, operations, intelligence, action, verification, reporting, and system surfaces;
- `types.ts` mirrors public response contracts only.

Frontend controls request server operations but cannot approve, execute, trust evidence, set roles/tenants, mark verification passed, or resolve locally. It renders `SIMULATED / CONTROLLED DEMONSTRATION` and safe source states.

## Extension and stop boundary

Future production work can replace repository/store implementations, add durable identity and source adapters, and integrate a SIEM without weakening the current service contracts. Phase 9 adds no new simulator action, production connector, unrestricted tool, or submission workflow. Phase 10 is explicitly not started.

See [security.md](security.md), [threat-model.md](threat-model.md), [actions.md](actions.md), and [verification.md](verification.md).
