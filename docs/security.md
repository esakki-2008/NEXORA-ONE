# NEXORA ONE security posture

NEXORA ONE treats an AI model as an untrusted planner, not as an operating-system user. Phase 3 adds real Nebius Token Factory and NVIDIA Nemotron inference without enabling orchestration or execution.

## Phase 3 controls

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
- Tools are explicit allow-list entries with input/output metadata, risk, and approval flags. Selected tools in an AI response must match the allow-list and are proposals only.
- The tool registry accepts bounded `ControlledTool` objects only. There is no arbitrary command, shell, subprocess, eval, Python, dynamic import, or model-supplied executable path.
- Phase 3 has no action executor, rollback, production mutation, autonomous orchestration, approval bypass, or verification executor.

## Failure and disclosure policy

API callers receive generic messages such as `Nebius authentication failed`, `AI provider request timed out`, or `AI response validation failed`. The API does not echo provider error bodies, request headers, prompts, model completions, or exception traces. The frontend displays backend status and concise lifecycle events only.

`AI CONNECTED` is shown only after a real `POST /api/ai/test` or analysis call receives a structured response that validates successfully. Configuration alone is not connectivity and is shown as not verified.

## Current application boundary

The existing local operator surface does not implement production user authentication or tenant authorization. That is an explicit limitation, not an implied security guarantee. Phase 3 provider authentication is server-to-Nebius bearer authentication only.

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

No Phase 3 code should be interpreted as authorization to execute a remediation action.
