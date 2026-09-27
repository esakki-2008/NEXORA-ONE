# NEXORA ONE security posture

NEXORA ONE treats an AI model as an untrusted planner, not as an operating-system user. Phase 5 reuses the real Phase 3 Nebius Token Factory and NVIDIA Nemotron service and the Phase 4 server-owned orchestrator, policy gate, fixed simulator actions, and verification boundary. Investigation adds evidence intelligence without adding an execution path.

## Phase 5 controls (plus Phase 1–4 controls)

- Secrets are loaded from environment variables through `pydantic-settings`.
- `.env`, local databases, private keys, and build artifacts are ignored.
- `NEBIUS_API_KEY` is represented as a server-side `SecretStr`. It is never defined as a frontend-exposed environment variable, sent to browser code, returned by `/api/ai/health`, added to activity metadata, or included in provider errors.
- The frontend makes only relative API requests. No frontend environment variable is used for the Nebius credential.
- The provider sends the key only in an outbound HTTPS `Authorization` header to the configured Nebius base URL. It does not log request headers, request bodies, or upstream response bodies.
- `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `NEBIUS_TIMEOUT_SECONDS`, and `NEBIUS_MAX_RETRIES` are server configuration. The model is not hardcoded and no alternate model vendor is used.
- Pydantic schemas reject unknown input fields, require exactly one analysis source, bound text/list/confidence values, and reject unsafe approval/tool metadata.
- Every model response must be a JSON object that passes `AIAnalysisResponse` validation before it is returned or used by the service; evidence IDs and hypothesis citations are grounded to the NEXORA-supplied evidence index and trusted evidence fields are copied server-side.
- Provider failures are typed and safe: authentication, model/provider availability, timeout, rejected request, malformed response, and missing configuration do not become fabricated answers.
- Retries are bounded and limited to transient timeout/network/408/429/5xx conditions. Authentication and schema failures are not retried.
- AI activity events contain only event type, safe status text, incident ID, source classification, and timestamps. Prompts, completions, chain-of-thought, credentials, and upstream bodies are excluded.
- ShopFlow Payment Failure and the other simulator fixtures are explicitly marked synthetic/demo data. They are read-only and cannot create or mutate live incidents.
- Phase 5 collection reuses only the existing read-only Phase 4 tool definitions plus the bounded non-mutating `run_test` probe. Investigation rejects arbitrary tool names before runtime dispatch; it has no second registry or executor.
- Evidence is treated as untrusted input. Normalization keeps bounded identifiers, source labels, timestamps, summaries, references, and metadata; it never executes logs/documentation or unsafe-deserializes evidence payloads.
- Every normalized record carries collector, collection status, source, raw reference, confidence/relevance, and an explicit simulator flag. Synthetic records are labeled `SIMULATED / CONTROLLED DEMONSTRATION` in the public source field.
- Correlations are deterministic relationships, not causal claims. Hypothesis statuses are server-owned and limited to `PROPOSED`, `TESTING`, `SUPPORTED`, `REJECTED`, and `INCONCLUSIVE`.
- Confidence is calculated server-side from explainable support, independence, relationship, quality, temporal, contradiction, and missing-evidence factors. AI confidence, lifecycle status, citations, and recommendations are validated/grounded and never authoritative.
- Missing/conflicting evidence, unavailable tools, malformed AI, low confidence, cancellation, and failed verification stop or escalate safely. A supported investigation can only hand off to the existing orchestrator; it cannot execute, approve, mutate, or mark an incident resolved.
- Investigation and request indexes are idempotent by incident/request ID. Repeated collection deduplicates evidence and repeated hypothesis generation deduplicates candidate titles within a run.
- Tools are explicit allow-list entries with input/output metadata, risk, and approval flags. Selected tools in an AI response must match the allow-list and are proposals only.
- The tool registry accepts bounded `ControlledTool` objects only. There is no arbitrary command, shell, subprocess, eval, Python, dynamic import, or model-supplied executable path.
- The Phase 4 context contains no prompt, completion, private reasoning, secret, or credential fields; public activity is concise and auditable.
- The explicit state machine rejects arbitrary jumps. `RESOLVED` is reachable only after successful verification; insufficient/conflicting evidence, unavailable tools, policy blocks, rejected/expired approvals, action failures, and verification failures escalate safely.
- `ToolPolicy` is server-owned. READ_ONLY tools may run automatically; only explicitly permitted LOW-risk tools may run without approval; MEDIUM/HIGH risk requires a valid server-side approval that covers the actual catalog risk.
- Every tool is allow-listed, enabled by server metadata, strictly validated with `extra="forbid"`, and returns a structured status, result, evidence, timestamp, risk, and execution ID.
- There is no shell, subprocess, `shell=True`, arbitrary Python, `eval`, `exec`, dynamic command, or model-generated command execution. The only state-changing actions are in-memory ShopFlow `restart_payment_service` and `rollback_simulated_deployment`, both marked `production_change: false`.
- Approval IDs and execution/idempotency keys prevent duplicate action execution. The frontend cannot grant approval, execute a tool, or mark an incident resolved independently.
- Phase 4 has an action executor only for the isolated simulator; it does not perform production mutation, real rollback, unrestricted autonomy, approval bypass, or resolution without verification.

## Failure and disclosure policy

API callers receive generic messages such as `Nebius authentication failed`, `AI provider request timed out`, or `AI response validation failed`. The API does not echo provider error bodies, request headers, prompts, model completions, or exception traces. The frontend displays backend status and concise lifecycle events only.

`AI CONNECTED` is shown only after a real `POST /api/ai/test` or analysis call receives a structured response that validates successfully. Configuration alone is not connectivity and is shown as not verified.

## Current application boundary

The existing local operator surface does not implement production user authentication or tenant authorization. That is an explicit limitation, not an implied security guarantee. Phase 3 provider authentication is server-to-Nebius bearer authentication only; Phase 4 approval identity is an auditable operator field, not a production authorization system. Phase 5 investigation provenance and request IDs are integrity and replay safeguards, not a replacement for authenticated operator identity or durable authorization.

## Required future hardening

Before production or autonomous action is enabled, add:

- authentication, tenant isolation, and role-based authorization;
- PostgreSQL with migrations, least-privilege credentials, encryption, and backups;
- secret manager integration and key rotation;
- structured audit sink with tamper resistance and retention policy;
- request size/rate limits, correlation IDs, idempotency, and abuse protection;
- prompt/context isolation, provider egress controls, sensitive-data redaction, and PII/payment-data policy;
- tool-specific authorization, dry-run support, rollback policy, approval expiry, and action allow-lists;
- durable verification records, provider/model allow-lists, and independent security review.

No Phase 4 or Phase 5 code should be interpreted as authorization to execute a production remediation action. Investigation handoff is a request into the Phase 4 boundary; it is not approval. Simulator execution is an isolated demonstration boundary only.
