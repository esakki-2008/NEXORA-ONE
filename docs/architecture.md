# NEXORA ONE foundation architecture

## Design goals

1. Keep domain models independent from HTTP, model vendors, and storage engines.
2. Make every agent, tool, action, and verification step explicit and auditable.
3. Prefer a bounded failure over fabricated AI output or an unapproved action.
4. Make Phase 3 provider integration additive rather than a rewrite.

## Backend boundaries

```text
backend/app/
├── api/            FastAPI routes and dependency wiring
├── agents/         agent contracts, registry, orchestrator boundary, state graph
├── ai/             provider-neutral request/decision contracts and provider boundary
├── config/         environment-backed settings
├── database/       repository port and Phase 1 in-memory adapter
├── models/         canonical domain records and enums
├── schemas/        HTTP input/output models
├── services/       application use cases
├── simulator/      structured ShopFlow fixtures
├── tools/          allow-listed tool definitions and registry
└── verification/   verification request/result contract
```

### API and services

Routes validate HTTP data using Pydantic and delegate to `IncidentService`. The service owns incident creation and looks up nested resources through `IncidentRepository`. Routes do not know whether storage is in memory or PostgreSQL.

### Database boundary

`IncidentRepository` is a protocol. `InMemoryIncidentRepository` is the Phase 1 reference adapter, designed for deterministic tests and a zero-dependency local start. A later PostgreSQL adapter can implement the same operations using the configured `DATABASE_URL`; consumers do not need to change.

### AI boundary

`AIRequest` and `StructuredAgentDecision` are the only objects an orchestrator should exchange with a model adapter. `AIProvider` is a protocol. `NebiusNemotronProvider` currently fails explicitly rather than making an untested network request. Phase 3 can implement HTTP transport, timeouts, authentication, structured-output validation, and observability behind that port.

### Agent boundary

`SpecialistAgent` is an abstract contract. `AgentDirectory` is an explicit registry. `AgentStateMachine` enforces the lifecycle:

```text
IDLE → INCIDENT_RECEIVED → OBSERVING → INVESTIGATING
     → HYPOTHESIS_GENERATED → VALIDATING → REMEDIATION_PROPOSED
     → WAITING_FOR_APPROVAL → EXECUTING → VERIFYING → RESOLVED
```

`FAILED`, `CANCELLED`, and `REQUIRES_HUMAN` are explicit terminal outcomes in Phase 1. No implicit retry or resume behavior is allowed.

### Tool boundary

Tool definitions carry input/output schemas, risk, and approval requirements. Only concrete `ControlledTool` instances can be registered and executed. The registry has no API for arbitrary shell commands, subprocesses, eval, or dynamic imports. Metadata for future tools is separate from executable implementations.

### Verification boundary

`VerificationRunner` accepts a structured `VerificationRequest` and returns a structured `VerificationResult`. This prevents an action from being considered successful merely because an invocation returned without an error.

## Frontend boundaries

The frontend is a Vite single-page app:

- `api/` contains relative-path API clients;
- `components/` contains shell, table, status, and empty/loading primitives;
- `pages/` contains route-level surfaces;
- `types.ts` mirrors only the public response contracts needed by Phase 1.

In development, Vite proxies `/health` and `/api` to the backend. Browser code never calls localhost directly; it calls relative paths so the same build works behind a preview host or reverse proxy.

## Extension path

- Phase 2 can add dashboard query services without changing incident records.
- Phase 3 can add a real Nebius/Nemotron adapter behind `AIProvider`.
- Phase 4 can register specialist agents and orchestrator policies.
- Phase 5 can persist evidence and hypotheses through repository extensions.
- Phase 6 can add domain-specific repositories and tools.
- Phase 7 can enable only approved `ControlledTool` actions.
- Phase 8 can persist verification records and report generation.
- Phase 9 can add durable Postgres storage, authentication, authorization, rate limits, and audit sinks.
