# NEXORA ONE — Phase 9 security hardening

Phase 9 is the server-side security boundary for the Phase 1–8 application. It does not add a second execution engine, rebuild completed phases, or start Phase 10. ShopFlow remains `SIMULATED / CONTROLLED DEMONSTRATION`; a reference token and in-memory stores are not production identity, storage, or audit infrastructure.

## Security goals and non-goals

The server must distinguish:

1. **Unauthenticated** — no valid bearer session; API access is rejected with `401`.
2. **Authenticated** — a valid server-signed principal establishes subject, tenant, roles, and expiry.
3. **Authorized** — server RBAC, actor binding, lifecycle state, exact resource relationships, and tenant scope permit the requested operation.

A frontend flag, hidden button, AI instruction, client risk, client approval, evidence trust value, verification status, or resolution field is never an authorization decision. AI, evidence, incident text, support text, logs, simulator content, and documentation are untrusted data.

This is a **REFERENCE SECURITY IMPLEMENTATION**. Production deployment must replace the reference token hook and local stores with an enterprise identity provider, durable tenant-aware storage, distributed rate limiting, centralized tamper-resistant audit, key rotation, and independent review.

## Authentication boundary

Every `/api/*` request is authenticated in the HTTP middleware before route handlers run. The intentionally public `/health` endpoint is liveness-only and returns no tenant or operational data.

The reference `TokenAuthenticator` uses an HMAC-signed compact bearer session. The signed payload contains only:

- `sub`: validated subject;
- `tenant`: validated tenant identifier;
- `roles`: one or more of `VIEWER`, `OPERATOR`, `APPROVER`, `ADMIN`;
- `iat`, `exp`, and `jti`.

Tokens have a bounded lifetime of 60 to 86,400 seconds, reject future-issued or oversized sessions, and are invalidated on a process restart when the server-only ephemeral key is used. `issue_reference_token()` is a server-side bootstrap/test hook; there is no unauthenticated token-minting route. The browser must never mint, sign, or interpret authorization.

`SECURITY_AUTH_SECRET` is loaded through `pydantic-settings`, represented as `SecretStr`, and never returned or logged. Production startup requires a non-empty value of at least 32 characters. Development/test may omit it, in which case the process generates an ephemeral server-only key. A production deployment must use a secret manager and rotation policy.

Safe responses are deliberately generic:

- `401 Authentication is required` for missing, malformed, expired, or incorrectly signed sessions;
- `403 Permission denied` for insufficient role or actor mismatch;
- `404` for an absent or out-of-tenant resource without confirming ownership;
- `409` for a valid request that conflicts with lifecycle or integrity state;
- `413` for a request body above the server limit;
- `429` with `Retry-After` for a bounded sensitive-route budget.

## RBAC and privileged authorization

Role permissions are defined in `backend/app/security/permissions.py`; roles are not inferred from a username and every authenticated user is not an administrator.

| Role | Intended authority |
| --- | --- |
| `VIEWER` | Read incidents, evidence, operations, reports, verification, and safe tool metadata |
| `OPERATOR` | Viewer access plus investigations, read-only collection, AI analysis, action proposals, execution after approval, cancellation, and bounded verification retry |
| `APPROVER` | Viewer access plus action review/approval, execution/cancellation, and bounded verification controls; it does not propose investigations by default |
| `ADMIN` | All reference permissions, including security-event visibility and security-configuration inspection |

The middleware maps HTTP method/path to a coarse permission before route code. Routes then apply exact authorization and resource checks. Privileged requests also bind the supplied actor to the authenticated subject; the body cannot impersonate an operator, approver, AI, or administrator.

Server-side gates cover:

- incident/investigation creation and cancellation;
- action proposal, approval, rejection, execution, cancellation, and rollback;
- orchestrator approval/rejection/cancellation;
- verification creation, run, retry, and cancellation;
- AI analysis and connectivity tests;
- security-event/configuration/integrity inspection;
- operations-to-investigation handoff.

Risk, approval state, action fingerprints, expected state, evidence trust, verification result, and incident resolution remain server-owned.

## Tenant isolation and resource relationships

Tenant identity is carried by the authenticated principal and is never accepted as a client override. The server propagates the same tenant through:

`user → tenant → incident → evidence/investigation → action → approval → execution → verification → report → audit/security event`.

The repository, action service, investigation store, orchestrator store, AI activity list, verification store, audit trail, and security-event list filter by tenant. Mutations require exact incident/action/investigation/approval/verification relationships. Cross-tenant reads and mutations return safe `404`/conflict responses and do not reveal whether another tenant owns the identifier. Security events generated by a denied request are tenant-scoped when an authenticated principal exists; anonymous authentication failures are not attributed to a tenant.

## AI and evidence security

AI is a bounded, untrusted planner:

- source normalization labels live and synthetic data explicitly;
- evidence, logs, incident text, simulator text, and support text are delimited as `<UNTRUSTED_DATA>` and never treated as policy instructions;
- injection indicators such as instruction override, fake administration, shell/tool execution, and approval requests are detected and recorded as `OBSERVED_AS_DATA`;
- every evidence/hypothesis citation must exist in the server-built evidence index;
- every selected tool must be in the foundation catalog, match server risk metadata, pass its strict input model, and satisfy incident/tenant bindings;
- nested `execute_safe_action` proposals are validated through the public seven-action registry without dispatching a runtime handler;
- recommended actions must be registered and must retain human approval;
- AI cannot set tenant, risk, policy, approval, execution, verification, rollback, or resolution state;
- AI activity is tenant-scoped and excludes prompts, completions, private reasoning, credentials, and upstream response bodies;
- the AI connectivity test validates its structured response too; a provider response is not a successful test merely because transport succeeded.

AI provider errors are typed and generic. Nebius configuration uses server-only `SecretStr`, bounded timeout/retries, JSON response validation, and an outbound HTTPS/SSRF validator. No arbitrary URL is accepted from an API caller.

## Registered tools and actions

`ToolRegistry` is the only runtime tool boundary. It contains explicit `ControlledTool` instances and strict Pydantic input models with `extra="forbid"`. Unknown names, arbitrary commands, callables, module names, paths, shell/process execution, dynamic imports, `eval`, `exec`, and unsafe deserialization are absent and rejected.

`ActionRegistry` is the only Phase 7 mutating boundary. It exposes exactly seven named ShopFlow actions with dedicated parameter models. The handler map binds constants; no request or AI output selects a Python method. Risk comes from registry metadata, not the client. Medium/high actions require a separate human approval, the requester cannot approve its own request, high-risk actions cannot auto-execute, and all proposals bind to a known incident and simulator scenario.

All actions remain simulated. A successful simulator change is not a production change and cannot resolve an incident without the Phase 8 proof gate.

## Evidence, verification, recovery, and integrity

Evidence records preserve source, collector, timestamp, raw reference, confidence/relevance, collection status, tenant, and simulator labels. Verification calculates expected/actual state through the action registry and read-only simulator boundary; clients cannot submit state, trust, confidence, or resolution claims.

The verification engine enforces:

- exact incident/action/fingerprint/scenario binding;
- explicit lifecycle transitions and stale-state protection;
- one to three bounded attempts with bounded backoff;
- serialized runs and idempotent action-to-verification binding;
- `TRUSTED`, `SIMULATED`, `UNTRUSTED`, and `UNAVAILABLE` evidence labels;
- freshness, contradiction, required-check, and confidence-factor gates;
- allow-listed recovery only, approval-gated rollback, and human escalation on unproven recovery;
- no resolution or report generation from execution success alone.

Action audit events, verification records/timelines, and security events are append-oriented and tamper-evident:

- action audit events use a per-action SHA-256 hash chain;
- verification records use an integrity hash and timeline previous/event hashes;
- security events use a tenant-aware global hash chain with safe metadata redaction.

Routes verify integrity before returning history. Tamper detection returns a safe `409`, emits a structured tamper event where possible, and never returns mutable internals or secrets.

## API hardening

The HTTP boundary applies:

- declared and streamed request-body limits (`SECURITY_MAX_REQUEST_BYTES`, default 256 KiB);
- bounded identifiers, text, collection sizes, AI output, retries, timeouts, and rate windows;
- strict Pydantic request/response schemas and unknown-field rejection;
- explicit HTTPS-only outbound URLs with credentials, fragments, non-443 ports, localhost, loopback, private, link-local, reserved, unspecified, and metadata targets blocked;
- explicit CORS origins with wildcard rejection and no credentials-enabled wildcard;
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and restrictive `Content-Security-Policy` headers;
- generic exception/provider messages and secret-safe metadata/log values;
- sensitive-route rate limits for AI, action creation/control, verification retries, and recovery.

The browser uses relative API paths and cannot call the backend over a client-side localhost URL. Vite's localhost proxy is a server-side development adapter only. The frontend displays server state; it does not grant roles or authorize actions.

## Structured security events

`SecurityEventType` includes authentication failures, authorization denials, cross-tenant access, invalid tool/action attempts, prompt-injection observations, rate-limit violations, oversized requests, tampered records, invalid state transitions, secret-exposure attempts, and configuration changes. Events contain a bounded actor/tenant/resource/source/result plus redacted metadata; prompts, tokens, provider bodies, and private reasoning are excluded.

`GET /api/security/events`, `/config`, and `/integrity` require `ADMIN`. Event reads are tenant-scoped. Security configuration reports safe limits/origins only and explicitly reports that secrets are absent.

## Threat-model summary

| Asset | Threat | Server control |
| --- | --- | --- |
| Tenant incident/evidence data | IDOR/cross-tenant enumeration | Principal tenant propagation, repository filters, safe not-found responses, negative tests |
| Action/approval authority | Actor spoofing, self-approval, AI approval | RBAC, exact actor binding, server risk/fingerprint/approval policy |
| Simulator/runtime | Arbitrary command or tool execution | Fixed registries, strict models, no shell/process/dynamic execution |
| AI context/output | Prompt injection, fabricated citations, unsafe recommendations | Untrusted-data framing, detection, evidence index, catalog/action validation |
| Provider/network | Credential leakage and SSRF | `SecretStr`, safe errors, HTTPS/host validation, bounded client |
| Audit/security history | Tampering or secret-bearing logs | Hash chains, immutable models, metadata redaction, integrity routes |
| API availability | Oversized, repeated, or slow input | Streaming limit, bounded schemas/timeouts/retries, rate limits |

See [threat-model.md](threat-model.md) for abuse cases and residual production risks.

## Validation evidence

The reference checkout validates with:

```bash
.venv/bin/pytest -q backend/tests                 # 157 passed
.venv/bin/ruff check backend                      # clean
.venv/bin/mypy backend/app                        # clean
.venv/bin/bandit -q -r backend/app                # clean
.venv/bin/pip-audit                               # no known vulnerabilities
cd frontend && npm run typecheck && npm run lint
cd frontend && npm run test -- --run && npm run build
./scripts/check_execution.sh
./scripts/check_secrets.sh
```

The Phase 9 security file contributes 85 passing negative/security cases; the complete backend suite preserves the Phase 1–8 regression tests.
