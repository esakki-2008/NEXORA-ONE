# Security foundation

NEXORA ONE treats an AI model as an untrusted planner, not as an operating-system user.

## Current controls

- Secrets are loaded from environment variables through `pydantic-settings`.
- `.env`, local databases, private keys, and build artifacts are ignored.
- The frontend receives no provider credentials and uses relative API requests.
- Pydantic schemas reject unknown incident input fields and enforce length/range constraints.
- The FastAPI surface exposes only the Phase 1 read/create routes.
- AI providers fail closed when not configured; no fake model answer is returned.
- Tools are explicit allow-list entries with schema metadata, risk, and approval flags.
- The tool registry accepts bounded tool objects only. There is no arbitrary command, shell, subprocess, eval, or code-generation execution path.
- Activity is recorded at incident intake, creating an audit-friendly event stream.
- Verification is a separate contract, so future actions must prove their effect.

## Future hardening requirements

Before production or autonomous action is enabled, add:

- authentication, tenant isolation, and role-based authorization;
- PostgreSQL with migrations, least-privilege credentials, encryption, and backups;
- secret manager integration and key rotation;
- structured audit sink with tamper resistance and retention policy;
- request size/rate limits, timeouts, idempotency keys, and correlation IDs;
- model response schema validation, prompt/context isolation, and provider egress controls;
- tool-specific authorization, dry-run support, rollback policy, and approval expiry;
- redaction of credentials, tokens, PII, and payment data before model/tool access;
- sandboxed integration tests and independent security review.

No Phase 1 code should be interpreted as authorization to execute a remediation action.
