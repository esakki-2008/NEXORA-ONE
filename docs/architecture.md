# NEXORA ONE architecture

Phase 3 preserves the Phase 1 foundation and Phase 2 Command Center while adding a server-only, validated Nebius/NVIDIA inference boundary.

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
├── ai/             Nebius/Nemotron provider, validated schemas, service, and lifecycle events
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
- `components/` contains the shell, icon set, tables, health cards, timelines, status, and loading/error/empty primitives;
- `hooks/` contains request lifecycle state with timeout/error/retry behavior;
- `lib/` contains display formatting and domain-source mapping only;
- `pages/` contains route-level command center, monitor, intelligence, action, reporting, and system surfaces;
- `types.ts` mirrors only public response contracts and simulator records.

Phase 2 uses real incident, activity, evidence, hypothesis, report, health, and simulator endpoints. Phase 3 extends the existing UI with backend-sourced AI health, a verified-only `AI CONNECTED` status, a safe Settings provider test, and the AI lifecycle activity feed. When a source is absent, the UI says so instead of manufacturing a score, provider connection, recommendation, or AI event. Simulator observations carry a visible synthetic/demo label and do not become live incident records.

In development, Vite proxies `/health` and `/api` to the backend. Browser code never calls localhost directly; it calls relative paths so the same build works behind a preview host or reverse proxy.

## Extension path

- Phase 2 can add dashboard query services without changing incident records.
- Phase 3 now provides the real Nebius/Nemotron adapter, validated response contract, health/test/analyze/activity routes, and mocked provider tests.
- Phase 4 can register specialist agents and orchestrator policies.
- Phase 5 can persist evidence and hypotheses through repository extensions.
- Phase 6 can add domain-specific repositories and tools.
- Phase 7 can enable only approved `ControlledTool` actions.
- Phase 8 can persist verification records and report generation.
- Phase 9 can add durable Postgres storage, authentication, authorization, rate limits, and audit sinks.
