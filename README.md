# NEXORA ONE

> **One AI operations brain for the entire business.**

NEXORA ONE is an autonomous enterprise operations AI platform foundation for the Nebius × NVIDIA Global AI Hackathon 2026, Best Apps & Agents track. It is designed for companies whose operational truth is distributed across applications, payments, databases, cloud infrastructure, support, supply chain, deployments, and compliance systems.

Phase 1 establishes the boundaries needed to observe, investigate, understand, correlate, prioritize, plan, request approval, act, verify, and report. Phase 2 builds the enterprise command center on those boundaries, connecting operational screens to real API and simulator data. Phase 3 adds the real Nebius Token Factory and NVIDIA Nemotron inference boundary with validated structured responses, bounded retries, and observable lifecycle events. Phase 4 adds the central stateful orchestrator, eight bounded specialists, deterministic policy, approval-gated simulator actions, verification, escalation, and incident reports.

## Problem

Modern companies have data everywhere, but investigation and action are fragmented. When revenue drops or an application fails, an operator may need to cross-reference deployments, logs, metrics, configuration, payment events, customer issues, and external dependencies manually. The cost is slower response, inconsistent decisions, and weak evidence trails.

## Solution

NEXORA ONE will become a controlled operations plane that coordinates a central orchestrator with bounded specialist agents, explicit tools, evidence, approval gates, controlled actions, verification, and incident reports:

```text
OBSERVE → INVESTIGATE → UNDERSTAND → CORRELATE → PRIORITIZE
                                      ↓
PLAN → REQUEST APPROVAL → ACT → VERIFY → REPORT
```

Phase 1 provides the contracts and runnable shell for that flow. Phase 2 provides the functional enterprise command center and connected read surfaces. Phase 3 performs bounded, evidence-grounded Nemotron analysis. Phase 4 lets the server orchestrate that analysis through an explicit state machine, but keeps the model as an untrusted planner: it cannot set permissions, approve, execute, bypass policy, or declare resolution.

## Why it matters

- **Faster resolution:** correlate signals instead of searching systems manually.
- **Safer autonomy:** allow-list tools, risk levels, approval gates, and verification keep actions bounded.
- **Traceable decisions:** evidence, hypotheses, activity, actions, and reports have explicit models.
- **Extensible enterprise scope:** the same orchestration boundaries can support IT, revenue, support, supply chain, contracts, cloud, data, and compliance domains.

## Architecture

```text
                         NEXORA ONE
                              │
                              ▼
                    ┌────────────────────┐
                    │  Agent Orchestrator│
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  Specialist agents     Controlled tools       Evidence ledger
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                     Approval-gated actions
                              │
                              ▼
                         Verification
                              │
                              ▼
                           Reports
```

The backend uses a repository port so domain services do not depend on a storage engine. Phase 1 includes a thread-safe in-memory reference adapter for local development and tests; the `DATABASE_URL` boundary is reserved for a PostgreSQL-compatible adapter without changing API or domain contracts.

See [docs/architecture.md](docs/architecture.md) for module boundaries and extension points.

## Agent architecture

The future orchestrator will dispatch to explicitly registered specialist agents:

- IT Operations Agent — incidents, logs, metrics, deployments, configuration
- Revenue Agent — payments, billing, checkout, revenue leakage
- Support Agent — tickets, customer issues, knowledge base, escalation
- Supply Chain Agent — suppliers, inventory, shipments, orders
- Contract Agent — obligations, renewals, penalties
- Cloud Agent — resources, usage, cost anomalies
- Data Agent — pipelines, data quality, anomalies
- Compliance Agent — controls, evidence, gaps

Phase 4 registers eight bounded specialist modules through an explicit directory: IT Operations, Revenue, Support, Supply Chain, Contracts, Cloud, Data, and Compliance. The central orchestrator owns deterministic routing, priorities, policy, approvals, action execution, verification, and escalation. See [docs/orchestrator.md](docs/orchestrator.md).

## Enterprise domains

The domain model starts with incidents, evidence, hypotheses, actions, approvals, verification, reports, services, deployments, and configuration changes. The simulator models ShopFlow services, deployments, configurations, metrics, logs, and transactions. Contracts for future domains can add records without changing the incident API boundary.

## Technology stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, async-ready provider/tool contracts
- **Database boundary:** PostgreSQL-compatible repository port; in-memory adapter for Phase 1 local runs
- **Testing:** pytest, FastAPI TestClient, Vitest, Testing Library, TypeScript checks
- **Configuration:** environment variables through `pydantic-settings`; no secrets in source

## Nebius + NVIDIA strategy

The Phase 3 inference path is fixed and server-only:

```text
Frontend → NEXORA Backend → NEXORA AI Service → Nebius Token Factory → NVIDIA Nemotron
                                                       ↓
                                  validated structured response → Command Center
```

`NebiusNemotronProvider` uses Nebius's OpenAI-compatible `/v1/chat/completions` HTTP contract through `httpx`. The model identifier is always supplied by `NEBIUS_MODEL`; no alternate vendor, local model, or hardcoded model output is used. Responses request JSON mode and are validated against `AIAnalysisResponse` before the service or frontend consumes them. Evidence references are grounded to the source evidence index and trusted source/summary fields are copied server-side; model output cannot introduce a new evidence record.

The analysis service accepts either a persisted live incident or a read-only ShopFlow fixture. It labels simulator context as `synthetic_demo_data`, sends only the selected source evidence, and emits concise lifecycle events without private model reasoning. Tool calls are allow-listed proposals from the existing catalog; Phase 3 never executes them.

Provider failures fail closed. Missing configuration, authentication failure, unavailable model/provider, timeout, rejected request, malformed JSON, and schema validation failure become typed safe errors. Retries are bounded by `NEBIUS_MAX_RETRIES` and only apply to transient transport/provider failures. `NEBIUS_API_KEY` remains a server-side `SecretStr` and is never placed in frontend code, API responses, activity metadata, or logs.

## Security model

Phase 4 preserves the Phase 1/2/3 controls and adds:

- environment-only configuration; `.env` is ignored and `.env.example` contains no credential values;
- `NEBIUS_API_KEY` is server-only and represented by `SecretStr`; it is absent from frontend bundles, responses, events, and provider error messages;
- Pydantic request and response validation with unknown fields rejected and every model response validated before use;
- generic, bounded API errors rather than stack traces, provider bodies, private reasoning, or secret-bearing logs;
- explicit `ToolDefinition` metadata with `risk_level` and `requires_approval`; selected tool proposals must match the allow-list;
- an allow-listed `ToolRegistry` with no arbitrary shell, subprocess, eval, Python, or model-supplied command execution;
- bounded provider retries, request timeouts, status-aware failures, and no fake success when configuration or connectivity is missing;
- observable AI lifecycle events containing only status/source metadata and concise messages;
- human approval remains required for risky recommendations; Phase 4 adds only fixed, simulator-scoped action execution;
- explicit verification contracts and a server-owned verification runner prevent resolution without proof;
- secret-free orchestration context, explicit transitions, deterministic routing/prioritization, hypothesis lifecycle, escalation, and auditable activity;
- eight controlled specialists, strict Pydantic tool argument validation, server-side READ_ONLY/LOW/MEDIUM/HIGH policy, idempotent approvals, and safe failure recovery;
- Command Center, Agents, Operations, Investigation, incident detail, Verification, action register, and report surfaces consume real orchestration endpoints.

See [docs/security.md](docs/security.md).

## Simulator

ShopFlow is a fictional company used for structured development fixtures. The read-only simulator exposes five scenarios:

1. Payment Failure — payment failures increase after a deployment.
2. Database Failure — application connections to the database fail.
3. Latency Spike — API response times increase.
4. Bad Deployment — a recent release introduces errors.
5. Configuration Mismatch — a configuration change causes failures.

The simulator contains structured services, deployments, configurations, metrics, logs, and transactions. Its public fixture API is read-only and never mutates incident records. Phase 4 may mutate an isolated in-memory fixture only through the two approval-gated actions documented in [docs/orchestrator.md](docs/orchestrator.md). Inspect fixtures through `GET /api/simulator/scenarios` and `GET /api/simulator/scenarios/{scenario_id}`.

## Current phase

**Phase 4 — Central Agent Orchestrator**

Phase 1 and Phase 2 remain intact. Phase 3 adds:

- premium enterprise command center with real incident and simulator source boundaries;
- grouped responsive navigation for monitoring, intelligence, action, reporting, and system surfaces;
- command center overview with API-backed active incidents, critical issue counts, observable activity, and simulator coverage;
- business health and operations views that distinguish no active records from not-configured domains;
- incident detail with impact context, lifecycle state visualization, evidence/hypothesis counts, and audit activity;
- evidence explorer with recorded-vs-simulator labels, search, and client-side filtering;
- investigation queue/detail surfaces that show structured evidence and hypotheses without exposing private model reasoning;
- honest agent directory, verification, reports, history, remediation boundary, and settings surfaces;
- loading skeletons, retryable errors, source-aware empty states, accessible controls, and responsive desktop/tablet/mobile behavior;
- frontend route coverage tests and production build verification;
- server-only Nebius/Nemotron provider verification and safe AI status in the existing Command Center;
- validated analysis for live incidents or clearly labeled synthetic ShopFlow evidence;
- provider test control in Settings, backend-sourced AI health, and observable AI lifecycle events;
- mocked provider tests covering success, retries, authentication, unavailable provider/model, timeout, malformed output, and missing configuration.

Still intentionally bounded or not implemented: production mutation, arbitrary shell/subprocess/Python execution, model-generated commands, approval bypass, fabricated evidence/activity/health, autonomous operation without an operator policy, durable orchestration persistence, production authentication/authorization, and an alternate AI provider. ShopFlow actions are synthetic in-memory demonstrations only.

## Ten-phase roadmap

| Phase | Scope |
| --- | --- |
| 1 | Foundation & Architecture |
| 2 | Enterprise Command Center |
| 3 | Nebius + NVIDIA AI Core |
| 4 | Enterprise Agent Orchestrator |
| 5 | Intelligence & Investigation Engine |
| 6 | Enterprise Operations Layer |
| 7 | Autonomous Action System |
| 8 | Verification & Continuous Learning |
| 9 | Security, Reliability & Production Hardening |
| 10 | Hackathon Finalization & Submission |

## Local development

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm

### Backend

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`; interactive docs are at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite development server is available at `http://localhost:5173`. Browser requests use relative `/health` and `/api` paths; Vite proxies them to the backend. No frontend secret is required.

### Environment variables

Copy `.env.example` to `.env`. The important variables are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Future PostgreSQL-compatible adapter URL; Phase 1 uses in-process storage |
| `NEBIUS_API_KEY` | Server-only Nebius Token Factory credential; never put this in frontend/Vite variables |
| `NEBIUS_MODEL` | NVIDIA Nemotron model identifier supplied at runtime |
| `NEBIUS_BASE_URL` | Nebius OpenAI-compatible base URL, normally including `/v1/` |
| `NEBIUS_TIMEOUT_SECONDS` | Provider request timeout; defaults to `60` |
| `NEBIUS_MAX_RETRIES` | Bounded transient retry count; defaults to `2` |
| `TAVILY_API_KEY` | Reserved for a future bounded research tool; unused in Phase 4 |
| `CORS_ORIGINS` | Comma-separated browser origins |

Never commit `.env` or credentials.

## API foundation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API availability and environment status |
| `POST` | `/api/incidents` | Create a validated incident |
| `GET` | `/api/incidents` | List incidents |
| `GET` | `/api/incidents/{id}` | Retrieve one incident |
| `GET` | `/api/incidents/{id}/activity` | Retrieve recorded activity |
| `GET` | `/api/incidents/{id}/evidence` | Retrieve evidence (empty until added by a future service) |
| `GET` | `/api/incidents/{id}/hypotheses` | Retrieve hypotheses (empty until added by a future service) |
| `GET` | `/api/incidents/{id}/report` | Retrieve a generated report; returns 404 when none exists |
| `GET` | `/api/simulator/scenarios` | List structured ShopFlow scenario fixtures |
| `GET` | `/api/simulator/scenarios/{scenario_id}` | Retrieve one read-only ShopFlow fixture |
| `GET` | `/api/ai/health` | Return safe Nebius configuration/last-verification status |
| `POST` | `/api/ai/test` | Make a real bounded structured Nemotron verification request |
| `POST` | `/api/ai/analyze` | Analyze one live incident or one synthetic ShopFlow scenario |
| `GET` | `/api/ai/activity` | Return concise observable AI lifecycle events; optionally filter by incident |
| `GET` | `/api/orchestrator/overview` | Return server-owned central orchestrator posture |
| `GET` | `/api/orchestrator/agents` | List eight registered specialist modules |
| `GET` | `/api/orchestrator/tools` | List enabled allow-listed tool metadata |
| `POST` | `/api/orchestrator/incidents/{id}/start` | Start live or explicit synthetic orchestration |
| `GET` | `/api/orchestrator/incidents/{id}` | Retrieve secret-free orchestration context |
| `GET` | `/api/orchestrator/incidents/{id}/activity` | Retrieve orchestration audit timeline |
| `GET` | `/api/orchestrator/incidents/{id}/hypotheses` | Retrieve hypothesis lifecycle records |
| `POST` | `/api/orchestrator/incidents/{id}/cancel` | Cancel an active workflow without executing a tool |
| `GET` | `/api/orchestrator/approvals` | List approval requests |
| `POST` | `/api/orchestrator/approvals/{id}/approve` | Approve through server policy and execute a fixed simulator action |
| `POST` | `/api/orchestrator/approvals/{id}/reject` | Reject and escalate without executing |
| `GET` | `/api/orchestrator/actions` | List controlled action executions |
| `GET` | `/api/orchestrator/verifications` | List verification results |

The Phase 4 frontend uses the AI health, orchestrator, approval, action, and verification surfaces without receiving credentials. The provider remains the existing Phase 3 Nebius/Nemotron service. The backend owns approvals, execution, idempotency, and resolution; the frontend only requests and renders those decisions.

## Testing and checks

Backend:

```bash
python -m pytest
ruff check backend
mypy backend/app
```

Frontend:

```bash
cd frontend
npm run test -- --run
npm run typecheck
npm run build
```

The repository also includes `scripts/check_secrets.sh` for a pre-commit credential scan.

## Git branch strategy

The planned phase sequence is:

```text
main
  ↓
phase-1-foundation
  ↓
phase-2-command-center
  ↓
phase-3-nebius-nvidia
  ↓
phase-4-agent-orchestrator
  ↓
phase-5-investigation
  ↓
phase-6-enterprise-operations
  ↓
phase-7-autonomous-actions
  ↓
phase-8-verification
  ↓
phase-9-security-hardening
  ↓
phase-10-submission
```

Each phase should be developed from the prior stable branch, tested, reviewed for secrets, committed with a meaningful message, pushed, and verified before the next phase begins. This Arena checkout is tracked on the session branch `arena/01a0dd8e-nexora-one`; it is kept separate from `main` and is not force-pushed or merged automatically.

## License

NEXORA ONE is released under the [MIT License](LICENSE).
