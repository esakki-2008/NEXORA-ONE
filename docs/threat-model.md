# NEXORA ONE Phase 9 threat model

This document describes the reference implementation's trust boundaries and residual risks. It covers Phase 9 only; no Phase 10 submission or production deployment work is included.

## System and trust boundaries

```text
untrusted browser / support text / logs / simulator text / AI output
                              │
                              ▼
        HTTP boundary: size → authentication → RBAC → rate limit
                              │
                              ▼
        tenant-scoped server services and strict Pydantic contracts
             │              │                 │
             ▼              ▼                 ▼
       AI normalizer   registered tools   action/approval plane
             │              │                 │
             └──────────────┼─────────────────┘
                            ▼
                  verification and recovery
                            │
                            ▼
              report/resolution only after proof
```

### Trusted server boundaries

- authenticated principal, after signature, expiry, role, subject, and tenant validation;
- server RBAC and actor binding;
- tenant/resource relationships checked against server-owned records;
- registered tool/action metadata and strict parameter models;
- simulator runtime state, read-only collectors, action fingerprints, approvals, and verification calculations;
- append-only audit/security history after integrity verification.

### Untrusted inputs

- bearer header before validation;
- all request JSON/query/path values;
- browser role/tenant/actor/risk/approval/status fields;
- incident titles/descriptions, support messages, logs, documentation, and simulator text;
- AI prompts, completions, citations, tool proposals, recommendations, and confidence;
- configured provider URL before SSRF validation;
- event metadata and error text.

## Abuse cases and controls

| ID | Abuse case | Consequence | Phase 9 control | Residual risk |
| --- | --- | --- | --- | --- |
| T01 | Missing, forged, expired, oversized, or foreign bearer token | Unauthenticated access or session confusion | HMAC validation, bounded payload, expiry, generic `401`, no token route | Reference HMAC must be replaced by enterprise IdP/JWKS and rotation |
| T02 | Viewer claims to be operator/admin | Unauthorized mutations or security-event disclosure | Explicit role-to-permission map, middleware and route gates, negative RBAC tests | Role provisioning is outside this local reference app |
| T03 | User supplies another actor, tenant, risk, approval, or verification state | Privilege escalation or false audit | Actor binding, principal tenant, server-owned risk/state, exact relationship checks | Durable identity and organization policy need external integration |
| T04 | Tenant A requests tenant B's incident/action/evidence/verification | Data disclosure or mutation | Tenant carried through repository/service/store/routes; safe `404`; cross-tenant tests | In-memory adapter is not durable multi-tenant storage |
| T05 | AI text says “ignore policy”, cites fabricated evidence, or asks to execute a command | Unsafe decision or fabricated proof | Untrusted-data delimiters, injection observation, evidence index, output schemas, catalogs, approval boundary | Detection is defense-in-depth, not a reason to trust AI text |
| T06 | AI or browser sends `shell`, arbitrary tool/action, callable, module, or path | Code execution or uncontrolled production action | Fixed registries, literal action names, strict inputs, no subprocess/eval/exec/dynamic import | Future integrations must preserve the same boundary |
| T07 | Provider URL points to localhost, cloud metadata, private IP, or includes credentials | SSRF or secret exposure | HTTPS-only URL validator blocks credentials, ports, private/link-local/reserved/metadata hosts | DNS rebinding and provider egress require network policy/allow-list in production |
| T08 | Oversized body, huge collections, repeated AI/action controls, or slow provider | Memory/CPU/resource exhaustion | Streaming body limit, bounded schemas, retries/timeouts, sensitive-route rate limiter | Distributed quotas and WAF are needed across replicas |
| T09 | Operator tampers with action audit, verification record/timeline, or security event | False history or hidden compromise | SHA-256 record/hash chains, append-only stores, safe `409`, tamper event | Local in-memory history is not a durable tamper-resistant audit sink |
| T10 | Secret appears in provider exception, event metadata, frontend bundle, or API response | Credential compromise | `SecretStr`, redaction, safe public errors, no provider body logging, scans | Secret managers, rotation, and DLP remain production requirements |
| T11 | Replay or duplicate action/verification request | Repeated mutation or inconsistent proof | Idempotency keys, exact fingerprints, locks, stale-state checks, bounded attempts | Persistent idempotency storage is required for multi-process deployment |
| T12 | Failed verification is treated as resolution | False recovery claim | Resolution gate requires fresh bound passed proof and complete trusted checks | External source attestations are not implemented in the simulator |
| T13 | CORS or browser navigation attempts privileged API use | Cross-origin abuse or clickjacking | Explicit origins, no wildcard, security headers, browser uses relative paths | CSRF/session strategy must be revisited if cookie auth replaces bearer sessions |
| T14 | Malformed path/query/body triggers stack trace or leaks existence | Information disclosure | Strict schemas, safe generic middleware errors, tenant-safe not-found behavior | Unexpected bugs still require monitoring and production exception handling |

## Security event expectations

The server records structured events for authentication failures, authorization/cross-tenant denials, invalid tool/action attempts, prompt injection, rate limits, oversized requests, tampering, and sensitive security conditions. Event metadata is bounded and redacted. Anonymous failures use `unknown` tenant rather than guessing ownership. Administrators can inspect only their tenant's event stream.

## Security test coverage

`backend/tests/test_security_hardening.py` contains 85 passing cases after parametrization, including:

- missing/malformed/foreign sessions and role separation;
- admin-only security configuration/event access;
- response headers and CORS restrictions;
- cross-tenant incident, action, approval, verification, AI, operations, and investigation access;
- actor spoofing and request-shape rejection;
- declared request limits and invalid content lengths;
- HTTPS/SSRF/provider credential checks;
- prompt-injection/redaction and AI evidence/action/tool output validation;
- registered-tool/action rejection and security events;
- rate limiting and audit/verification/security-event tamper detection.

## Residual production work

This reference implementation must not be interpreted as production authorization. Before deployment, add an enterprise IdP with short-lived tokens and key discovery/rotation, durable tenant-scoped persistence with database-level policies, distributed rate limits and locks, allow-listed egress/network controls including DNS rebinding defense, centralized immutable audit retention, secret manager/DLP integration, privacy/data-retention policy, monitoring/SIEM integration, formal threat-model review, and penetration testing.
