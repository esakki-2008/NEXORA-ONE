# NEXORA ONE

> **One AI operations brain for the entire business.**

NEXORA ONE is an autonomous enterprise operations AI platform foundation for the Nebius × NVIDIA Global AI Hackathon 2026, Best Apps & Agents track. It is designed for companies whose operational truth is distributed across applications, payments, databases, cloud infrastructure, support, supply chain, deployments, and compliance systems.

Phase 1 establishes the boundaries needed to observe, investigate, understand, correlate, prioritize, plan, request approval, act, verify, and report without pretending that later capabilities already exist. Phase 2 builds the enterprise command center on those boundaries, connecting operational screens to real API and simulator data.

## Problem

Modern companies have data everywhere, but investigation and action are fragmented. When revenue drops or an application fails, an operator may need to cross-reference deployments, logs, metrics, configuration, payment events, customer issues, and external dependencies manually. The cost is slower response, inconsistent decisions, and weak evidence trails.

## Solution

NEXORA ONE will become a controlled operations plane that coordinates a central orchestrator with bounded specialist agents, explicit tools, evidence, approval gates, controlled actions, verification, and incident reports:

```text
OBSERVE → INVESTIGATE → UNDERSTAND → CORRELATE → PRIORITIZE
                                      ↓
PLAN → REQUEST APPROVAL → ACT → VERIFY → REPORT
```

Phase 1 provides the contracts and runnable shell for that flow. Phase 2 provides the functional enterprise command center and connected read surfaces. The product still intentionally does **not** run an autonomous investigation, call an AI provider, or execute remediation.

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

Phase 1 includes a `SpecialistAgent` contract, `AgentDirectory`, orchestrator dependency boundary, and reusable state machine. No specialist implementation is registered yet.

## Enterprise domains

The domain model starts with incidents, evidence, hypotheses, actions, approvals, verification, reports, services, deployments, and configuration changes. The simulator models ShopFlow services, deployments, configurations, metrics, logs, and transactions. Contracts for future domains can add records without changing the incident API boundary.

## Technology stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, async-ready provider/tool contracts
- **Database boundary:** PostgreSQL-compatible repository port; in-memory adapter for Phase 1 local runs
- **Testing:** pytest, FastAPI TestClient, Vitest, Testing Library, TypeScript checks
- **Configuration:** environment variables through `pydantic-settings`; no secrets in source

## Nebius + NVIDIA strategy

The target inference path is fixed:

```text
NEXORA orchestrator → Nebius Token Factory → NVIDIA Nemotron → structured decision
```

Phase 1 has a provider-neutral `AIProvider` contract, a typed request/decision envelope, and explicit unconfigured/Nebius-Nemotron adapter boundaries. It makes no network call and returns no fabricated answer. Phase 3 will add the real Nebius transport and structured response validation; it will not replace the target architecture with OpenAI, Gemini, Claude, OpenRouter, or Ollama.

## Security model

Phase 1 establishes the following controls:

- environment-only configuration; `.env` is ignored and `.env.example` contains no values;
- no API keys are exposed to the frontend;
- Pydantic request and response validation with unknown input fields rejected;
- generic, bounded API errors rather than stack traces or secret-bearing logs;
- explicit `ToolDefinition` metadata with `risk_level` and `requires_approval`;
- an allow-listed `ToolRegistry` with no arbitrary shell, subprocess, eval, or model-supplied command execution;
- activity records that create an audit-friendly trail;
- explicit verification contracts for proving a controlled action changed the expected state.

See [docs/security.md](docs/security.md).

## Simulator

ShopFlow is a fictional company used for structured development fixtures. The read-only simulator exposes five scenarios:

1. Payment Failure — payment failures increase after a deployment.
2. Database Failure — application connections to the database fail.
3. Latency Spike — API response times increase.
4. Bad Deployment — a recent release introduces errors.
5. Configuration Mismatch — a configuration change causes failures.

The simulator contains structured services, deployments, configurations, metrics, logs, and transactions. It is not a fake dashboard and does not mutate incident records. Inspect it through `GET /api/simulator/scenarios` and `GET /api/simulator/scenarios/{scenario_id}`.

## Current phase

**Phase 2 — Enterprise Command Center**

Phase 1 remains intact and Phase 2 adds:

- premium enterprise command center with real incident and simulator source boundaries;
- grouped responsive navigation for monitoring, intelligence, action, reporting, and system surfaces;
- command center overview with API-backed active incidents, critical issue counts, observable activity, and simulator coverage;
- business health and operations views that distinguish no active records from not-configured domains;
- incident detail with impact context, lifecycle state visualization, evidence/hypothesis counts, and audit activity;
- evidence explorer with recorded-vs-simulator labels, search, and client-side filtering;
- investigation queue/detail surfaces that show structured evidence and hypotheses without exposing private model reasoning;
- honest agent directory, verification, reports, history, remediation boundary, and settings surfaces;
- loading skeletons, retryable errors, source-aware empty states, accessible controls, and responsive desktop/tablet/mobile behavior;
- frontend route coverage tests and production build verification.

Still intentionally not implemented: autonomous investigation, specialist agent execution, real model calls, remediation execution, approval workflows, verification execution, fake metrics, fabricated AI activity, or production authentication.

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
| `NEBIUS_API_KEY` | Reserved for the Phase 3 Nebius Token Factory adapter |
| `NEBIUS_MODEL` | Reserved NVIDIA Nemotron model identifier |
| `NEBIUS_BASE_URL` | Reserved Nebius endpoint |
| `TAVILY_API_KEY` | Reserved for a future bounded research tool |
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

The Phase 2 frontend uses these existing read surfaces. Future endpoints such as investigate, approve, execute, and verify are deliberately not registered yet.

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
