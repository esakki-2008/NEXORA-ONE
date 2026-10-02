# NEXORA ONE

> **One AI operations brain for the entire business.**

NEXORA ONE is an autonomous enterprise operations AI platform foundation for the Nebius × NVIDIA Global AI Hackathon 2026, Best Apps & Agents track. It is designed for companies whose operational truth is distributed across applications, payments, databases, cloud infrastructure, support, supply chain, deployments, and compliance systems.

Phase 1 establishes the boundaries needed to observe, investigate, understand, correlate, prioritize, plan, request approval, act, verify, and report. Phase 2 builds the enterprise command center on those boundaries, connecting operational screens to real API and simulator data. Phase 3 adds the real Nebius Token Factory and NVIDIA Nemotron inference boundary with validated structured responses, bounded retries, and observable lifecycle events. Phase 4 adds the central stateful orchestrator, eight bounded specialists, deterministic policy, approval-gated simulator actions, verification, escalation, and incident reports. Phase 5 adds evidence intelligence: provenance-preserving collection, deterministic correlation, server-scored hypotheses, confidence factors, gaps, root-cause candidates, timeline, and guarded handoff back to the Phase 4 orchestrator. Phase 6 adds a unified enterprise operations intelligence layer across IT, revenue, support, supply chain, contracts, cloud, data, and compliance without creating separate domain applications or a second action path. Phase 7 adds a single controlled autonomous-action plane: seven allow-listed ShopFlow simulator actions, server-calculated risk, immutable fingerprints, human approval, bounded execution, rollback, verification, idempotency, audit chaining, and report-integrated resolution. Phase 8 extends that verification boundary into a strongly typed reliability engine with explicit lifecycle states, deterministic expected-versus-actual checks, provenance-aware evidence, bounded retries, recovery/rollback verification, human escalation, and a strict resolution proof gate. **Phase 9 hardens every server boundary with reference authentication, explicit RBAC, tenant isolation, AI/evidence validation, SSRF and request limits, structured security events, integrity checks, safe errors, rate limits, and negative security coverage.**

## Problem

Modern companies have data everywhere, but investigation and action are fragmented. When revenue drops or an application fails, an operator may need to cross-reference deployments, logs, metrics, configuration, payment events, customer issues, and external dependencies manually. The cost is slower response, inconsistent decisions, and weak evidence trails.

## Solution

NEXORA ONE will become a controlled operations plane that coordinates a central orchestrator with bounded specialist agents, explicit tools, evidence, approval gates, controlled actions, verification, and incident reports:

```text
OBSERVE → INVESTIGATE → UNDERSTAND → CORRELATE → PRIORITIZE
                                      ↓
PLAN → REQUEST APPROVAL → ACT → VERIFY → REPORT
```

Phase 1 provides the contracts and runnable shell for that flow. Phase 2 provides the functional enterprise command center and connected read surfaces. Phase 3 performs bounded, evidence-grounded Nemotron analysis. Phase 4 lets the server orchestrate that analysis through an explicit state machine, but keeps the model as an untrusted planner: it cannot set permissions, approve, execute, bypass policy, or declare resolution. Phase 5 makes investigation independently auditable while preserving the same server-owned approval, controlled-action, verification, and resolution boundaries. Phase 7 makes the action boundary explicit and reviewable: an AI recommendation can become only a server-validated proposal, and a verified simulator outcome is required before resolution.

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

See [docs/architecture.md](docs/architecture.md) for module boundaries and extension points. See [docs/investigation.md](docs/investigation.md) for the Phase 5 workflow, contracts, evidence provenance, deterministic scoring, APIs, and safe handoff behavior. See [docs/actions.md](docs/actions.md) for the Phase 7 registry, lifecycle, safety controls, API, and payment-failure demonstration path. See [docs/verification.md](docs/verification.md) for the Phase 8 verification lifecycle, evidence trust, confidence factors, retry/recovery policy, resolution gate, API, UI, and tests.

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

The domain model starts with incidents, evidence, hypotheses, actions, approvals, verification, reports, services, deployments, and configuration changes. Phase 6 adds strict operations contracts for domain health, source metadata, operational signals, metrics, service health, business impact, correlations, priorities, events, and snapshots. The simulator models ShopFlow services, deployments, configurations, metrics, logs, transactions, and an explicit synthetic support observation. Contracts for future domain adapters can add records without changing the unified operations API boundary. Missing sources are returned as `NOT_CONFIGURED`; no health or business value is inferred from absence.

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

Phase 9 is the completed security-hardening phase. Controls are server-side and apply even when a frontend, simulator fixture, support message, evidence record, or AI response is malicious or misleading:

- **Reference authentication:** every `/api/*` request requires a server-signed bearer session. The token carries only a validated subject, tenant, roles, issue/expiry times, and token ID. Missing or invalid sessions are `401`; a valid session is not automatically authorized.
- **Explicit RBAC:** `VIEWER`, `OPERATOR`, `APPROVER`, and `ADMIN` have separate permission sets. Privileged proposal, investigation, approval, execution, rollback, cancellation, verification, AI, configuration, and security-event operations are checked before route logic.
- **Reference deployment boundary:** `SECURITY_AUTH_SECRET` is a secret-manager/environment value and must be at least 32 characters in production. If it is absent in development/test, an ephemeral server-only key is used and all sessions expire on restart. There is no token-minting API; `issue_reference_token()` is a server-side bootstrap/test hook only.
- **Tenant isolation:** incidents, evidence, investigations, actions, approvals, orchestrations, verifications, reports, AI activity, audit events, and security events carry tenant bindings. Repositories and routes filter or reject cross-tenant reads and mutations server-side.
- **Untrusted AI boundary:** evidence and incident text are delimited as data, injection indicators are recorded, evidence citations must exist in the server-built index, and AI cannot set risk, tenant, policy, approval, execution, verification, or resolution state. AI tools/actions are checked against the registered catalogs and exact resource bindings.
- **Execution boundary:** only registered read-only tools and seven registered simulator actions can run. Arbitrary tool names, commands, callables, shell/process execution, filesystem execution, and frontend-direct execution are not exposed.
- **Evidence and recovery trust:** provenance, simulator labels, freshness, contradiction, expected/actual state, approval, action fingerprint, rollback, verification, and resolution are calculated by the server. Execution success alone never resolves an incident.
- **API hardening:** bounded streamed request bodies, strict schemas and unknown-field rejection, bounded identifiers/collections/retries/timeouts, HTTPS-only outbound provider URLs, credential/private/link-local/metadata SSRF blocks, restricted CORS, security headers, generic provider errors, and sensitive-route rate limits are enforced at the request boundary.
- **Integrity and observability:** action audits, verification timelines, and security events are append-only hash chains. Tamper detection returns a safe conflict, records a structured event where possible, and never returns secrets or private model reasoning.
- **Demonstration labeling:** ShopFlow remains `SIMULATED / CONTROLLED DEMONSTRATION`; reference authentication and in-memory stores are explicitly not a production identity provider or durable security log.

See [docs/security.md](docs/security.md) and [docs/threat-model.md](docs/threat-model.md).

## Simulator

ShopFlow is a fictional company used for structured development fixtures. The read-only simulator exposes five scenarios:

1. Payment Failure — payment failures increase after a deployment.
2. Database Failure — application connections to the database fail.
3. Latency Spike — API response times increase.
4. Bad Deployment — a recent release introduces errors.
5. Configuration Mismatch — a configuration change causes failures.

The simulator contains structured services, deployments, configurations, metrics, logs, transactions, queues, feature flags, and bounded service capacities. Its public fixture API is read-only and never mutates incident records. Phase 5 investigation and Phase 6 operations records label collected fixture evidence `SIMULATED / CONTROLLED DEMONSTRATION` and preserve source/collector/reference metadata. Phase 4 retains its existing two approval-gated simulator tools; Phase 7 adds seven separately registered controlled actions that mutate only an in-memory fixture and are verified/rolled back through the Phase 7 action service. Inspect fixtures through `GET /api/simulator/scenarios` and `GET /api/simulator/scenarios/{scenario_id}`. See [docs/operations.md](docs/operations.md) and [docs/actions.md](docs/actions.md) for the boundaries.

## Current phase

**Phase 9 — Security Hardening**

Phase 9 stops here; Phase 10 is not started. The hardening deliverable includes:

- server-side reference authentication with unauthenticated/authenticated/authorized states and explicit `VIEWER`, `OPERATOR`, `APPROVER`, and `ADMIN` RBAC;
- authorization and actor binding for privileged investigation, action, approval, execution, rollback, cancellation, verification, AI, configuration, and administrative operations;
- tenant-bound incidents, evidence, investigations, actions, approvals, orchestrations, verifications, reports, AI activity, audit records, and security events with cross-tenant negative coverage;
- prompt-injection framing/detection, evidence-index grounding, registered tool/action validation, resource and tenant binding, output/risk/approval validation, and no AI authority over execution or resolution;
- request streaming limits, bounded inputs/resources/retries/timeouts, HTTPS/SSRF validation, restricted CORS, security headers, safe provider errors, rate limits, secret-safe logs, and forbidden-execution scanning;
- append-only action-audit, verification-timeline, and security-event integrity chains with safe tamper responses and structured security events;
- 157 backend tests, including 85 Phase 9 security-hardening cases, plus frontend regression/type/build checks and dependency/security scans.

All Phase 1–8 flows remain simulator-backed where applicable and preserve the `SIMULATED / CONTROLLED DEMONSTRATION` label. The in-memory repository, reference token hook, and local security-event store are explicit reference implementations that require production identity, durable storage, distributed rate limiting, and centralized audit infrastructure before deployment.

## Roadmap through Phase 9

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Foundation & Architecture | Complete |
| 2 | Enterprise Command Center | Complete |
| 3 | Nebius + NVIDIA AI Core | Complete |
| 4 | Enterprise Agent Orchestrator | Complete |
| 5 | Intelligence & Investigation Engine | Complete |
| 6 | Enterprise Operations Layer | Complete |
| 7 | Autonomous Action System | Complete |
| 8 | Verification & Reliability Engine | Complete |
| 9 | Security Hardening | Complete for this reference implementation |
| 10 | Submission | Not started |

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

The Vite development server is available at `http://localhost:5173`. Browser requests use relative `/health` and `/api` paths; Vite proxies them to the backend. The browser never decides authorization. For the documented reference deployment, set a short-lived `VITE_NEXORA_AUTH_TOKEN` only through local/runtime environment injection; do not commit or treat it as a production credential. A production frontend must integrate with the organization identity provider and send its server-validated bearer session.

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
| `VERIFICATION_MAX_ATTEMPTS` | Phase 8 verification attempt bound; defaults to `3` |
| `VERIFICATION_RETRY_DELAY_SECONDS` | Deterministic verification retry backoff base; defaults to `0.01` |
| `VERIFICATION_MAX_EVIDENCE_AGE_SECONDS` | Freshness gate for resolution proof; defaults to `300` |
| `TAVILY_API_KEY` | Reserved for a future bounded research tool; unused in Phase 9 |
| `SECURITY_AUTH_SECRET` | Server-only HMAC secret, minimum 32 characters; required in production |
| `SECURITY_TOKEN_TTL_SECONDS` | Reference bearer-session lifetime, bounded to 60–86,400 seconds |
| `SECURITY_MAX_REQUEST_BYTES` | Declared and streamed request-body limit, default `262144` |
| `CORS_ORIGINS` | Comma-separated explicit browser origins; wildcard is rejected |

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
| `GET` | `/api/investigations` | List Phase 5 investigation summaries |
| `POST` | `/api/investigations/incidents/{id}/start` | Start an idempotent live or controlled ShopFlow investigation |
| `GET` | `/api/investigations/incidents/{id}` | Retrieve the investigation for an incident |
| `GET` | `/api/investigations/{id}` | Retrieve evidence, correlations, hypotheses, gaps, candidates, and timeline |
| `GET` | `/api/investigations/{id}/summary` | Retrieve a compact investigation summary |
| `GET` | `/api/investigations/{id}/evidence` | List normalized evidence with provenance |
| `GET` | `/api/investigations/{id}/correlations` | List deterministic non-causal correlations |
| `GET` | `/api/investigations/{id}/hypotheses` | List server-scored hypothesis lifecycle records |
| `GET` | `/api/investigations/{id}/timeline` | List investigation audit events |
| `POST` | `/api/investigations/{id}/collect` | Collect additional allow-listed read-only evidence |
| `POST` | `/api/investigations/{id}/test-hypothesis` | Test one hypothesis with bounded probes |
| `POST` | `/api/investigations/{id}/handoff` | Hand off to Phase 4 policy/approval orchestration |
| `POST` | `/api/investigations/{id}/cancel` | Cancel without executing an action |
| `GET` | `/api/operations/snapshot` | Get the deterministic eight-domain operations snapshot; optional `scenario_id`/`incident_id` |
| `POST` | `/api/operations/refresh` | Manually refresh the operations snapshot |
| `GET` | `/api/operations/domains` | List all domain health records |
| `GET` | `/api/operations/domains/{domain}` | Retrieve metrics, signals, incidents, evidence, impact, and correlations for one domain |
| `GET` | `/api/operations/signals` | List operational signals; optional domain/source filters |
| `GET` | `/api/operations/signals/{id}` | Retrieve one signal |
| `POST` | `/api/operations/signals/{id}/investigate` | Open an existing Phase 5 investigation without executing an action |
| `GET` | `/api/operations/correlations` | List non-causal cross-domain related-signal records |
| `GET` | `/api/operations/priorities` | List explainable server-generated priorities |
| `GET` | `/api/operations/business-impact` | Retrieve deterministic business impact |
| `GET` | `/api/operations/health` | Retrieve configured/not-configured source status |
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
| `GET` | `/api/orchestrator/verifications` | List legacy orchestrator verification summaries |
| `GET` | `/api/verification` | List Phase 8 verification records; optional status/incident/action filters |
| `GET` | `/api/verification/summary` | Return Phase 8 reliability counts and success rate |
| `POST` | `/api/verification` | Create a record from a server-known action identity |
| `GET` | `/api/verification/{id}` | Retrieve one integrity-checked Phase 8 record |
| `POST` | `/api/verification/{id}/run` | Run one bounded server-owned verification attempt |
| `POST` | `/api/verification/{id}/retry` | Run the next bounded retry with deterministic backoff |
| `POST` | `/api/verification/{id}/cancel` | Cancel a safe non-terminal verification |
| `GET` | `/api/verification/{id}/evidence` | Retrieve provenance-aware proof evidence |
| `GET` | `/api/verification/{id}/timeline` | Retrieve the append-only hash-chained timeline |
| `GET` | `/api/security/session` | Return the authenticated subject, tenant, roles, state, and expiry without a token |
| `GET` | `/api/security/events` | List only the authenticated tenant's structured security events; requires `ADMIN` |
| `GET` | `/api/security/config` | Inspect safe security configuration; requires `ADMIN` |
| `GET` | `/api/security/integrity` | Check the tenant-scoped security-event chain; requires `ADMIN` |

Except for the intentionally public `/health` liveness endpoint, `/api/*` requires `Authorization: Bearer <server-issued-reference-session>`. `401` means the request is not authenticated; `403` means the authenticated role or actor is not authorized; `404` is used for out-of-tenant resources without confirming ownership. The route body never grants a role or tenant.

The Phase 4 frontend uses the AI health, orchestrator, approval, action, and verification surfaces without receiving credentials. The Phase 6 frontend additionally renders the unified Operations snapshot, domain detail, signals, priorities, impact, and correlations. The provider remains the existing Phase 3 Nebius/Nemotron service. The backend owns approvals, execution, idempotency, and resolution; the frontend only requests and renders those decisions.

## Frontend routes

- `/command-center` — enterprise status, domain health, critical signals, business impact, deterministic priorities, correlations, incident intake, and AI activity;
- `/operations` — high-density eight-domain operations dashboard with manual ShopFlow scenario selection and refresh;
- `/operations/{domain}` — domain metrics, signals, related incidents/evidence, impact, correlations, and guarded Phase 5 investigation entry;
- `/remediation` — Controlled Actions registry, proposal intake, approval queue, risk posture, and action ledger;
- `/remediation/{actionId}` — Action Detail with fingerprint review, human approval controls, bounded execution/rollback, verification, and hash-chained audit;
- `/verification` — Phase 8 verification overview with reliability counts, proof register, and action bindings;
- `/verification/{verificationId}` — expected/actual state, deterministic checks, confidence factors, provenance evidence, bounded controls, and timeline hashes;
- `/incidents`, `/investigation`, `/evidence`, `/agents`, `/reports`, `/history`, and `/settings` — existing Phase 1–7 surfaces preserved and linked to Phase 8 proof.

## Testing and checks

Backend:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check backend
.venv/bin/mypy backend/app
.venv/bin/bandit -q -r backend/app
.venv/bin/pip-audit
./scripts/check_execution.sh
./scripts/check_secrets.sh
```

The Phase 9 backend suite includes 157 passing tests, including 85 security-hardening cases covering authentication, RBAC, actor binding, tenant isolation, request limits, SSRF, AI/evidence validation, registered tools/actions, rate limits, safe errors, and integrity tampering.

Frontend:

```bash
cd frontend
npm ci
npm run test -- --run
npm run typecheck
npm run lint
npm run build
```

The repository includes `scripts/check_secrets.sh` for a pre-commit credential scan; the complete check runner also executes `pip-audit`, Bandit, `npm audit`, and static scans for arbitrary execution and frontend credentials.

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
