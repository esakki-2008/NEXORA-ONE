# NEXORA ONE — hackathon submission checklist

This page is a submission worksheet, not a claim that a public deployment or video already exists. Replace bracketed placeholders only with verified details before submitting. Do not add credentials, private URLs, or invented model identifiers.

## Submission identity

- [ ] Project name: **NEXORA ONE**
- [ ] Hackathon: **Nebius × NVIDIA Global AI Hackathon 2026**
- [ ] Track: **Best Apps & Agents**
- [ ] Team / author: `[ADD VERIFIED TEAM DETAILS]`
- [ ] Contact: `[ADD VERIFIED CONTACT]`
- [ ] Repository URL: `[ADD VERIFIED PUBLIC REPOSITORY URL]`
- [ ] Live demo URL, if actually deployed: `[ADD VERIFIED LIVE DEMO URL OR STATE NOT DEPLOYED]`
- [ ] Demo video URL, if recorded: `[ADD VERIFIED VIDEO URL]`
- [ ] Submission form URL or confirmation: `[ADD VERIFIED SUBMISSION REFERENCE]`

## Required story

- [ ] Problem: operational truth is distributed across incidents, payments, deployments, metrics, support, and enterprise systems.
- [ ] Solution: one evidence-grounded operations plane that observes, investigates, correlates, proposes, requests approval, acts in a controlled boundary, verifies, and reports.
- [ ] AI contribution: NEXORA sends bounded context through the server-side `AIService` and `NebiusNemotronProvider` to **Nebius Token Factory** for **NVIDIA Nemotron** structured assistance.
- [ ] Model configuration: identify the model only from the verified runtime `NEBIUS_MODEL` value; do not invent or hardcode a model identifier in this worksheet.
- [ ] Demo workflow: ShopFlow `payment-failure`, clearly labeled **SIMULATED / CONTROLLED DEMONSTRATION**.
- [ ] Safety story: AI is an untrusted planner; server-side RBAC, tenant isolation, evidence grounding, registered action/tool validation, approval, verification, rollback, idempotency, audit integrity, rate limits, SSRF controls, and safe errors remain authoritative.

## Architecture and deployment

- [ ] Architecture shown: `Frontend → NEXORA Backend → Nebius Token Factory → NVIDIA Nemotron`.
- [ ] Low-cost path documented: static frontend hosting plus one small backend service plus Nebius Token Factory; no GPU service is operated by NEXORA.
- [ ] Secrets are server-side: `NEBIUS_API_KEY` is injected into the backend runtime only and is never placed in frontend/Vite variables, logs, activity, errors, screenshots, or this submission.
- [ ] Required backend variables reviewed from `.env.example`: `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `NEBIUS_TIMEOUT_SECONDS`, `NEBIUS_MAX_RETRIES`, `SECURITY_AUTH_SECRET`, `SECURITY_TOKEN_TTL_SECONDS`, `SECURITY_MAX_REQUEST_BYTES`, and `CORS_ORIGINS`.
- [ ] Production deployment review completed: replace reference authentication, in-memory persistence, in-memory rate limiting, and local audit storage with production services before making a production claim.

## Verification evidence

- [ ] `scripts/verify_nebius_runtime.py` was run in the target runtime.
- [ ] Live-provider result recorded without a secret: `[RECORD PASSED / SAFE FAILURE / NOT EXECUTED]`.
- [ ] Configured base URL recorded privately for the release record: `[ADD VERIFIED VALUE OR REDACTED HOST DESCRIPTION]`.
- [ ] Configured model recorded from `NEBIUS_MODEL`: `[ADD VERIFIED VALUE]`.
- [ ] Structured response schema validation result: `[ADD VERIFIED RESULT]`.
- [ ] Evidence grounding result: `[ADD VERIFIED RESULT]`.
- [ ] Registered action/tool validation result: `[ADD VERIFIED RESULT]`.
- [ ] Timeout and safe-provider-failure result: `[ADD VERIFIED TEST/RUNTIME RESULT]`.
- [ ] No chain-of-thought or private reasoning is included in screenshots or copy.

## Demo evidence

- [ ] Command Center shows observable AI lifecycle events with provider, model, purpose, status, timestamp, and incident/context.
- [ ] ShopFlow evidence and business impact are shown with the simulator label.
- [ ] Recommendation is shown as a server-validated proposal, not an authorization.
- [ ] Human approval is shown before the controlled action.
- [ ] Verification proof, expected/actual checks, audit timeline, resolution, and report are shown.
- [ ] Failure-path evidence shows verification failure, rollback, bounded retry, and human escalation.
- [ ] Demo script used: [docs/demo-script.md](demo-script.md).

## Release validation checklist

- [ ] Backend tests pass, including Phase 9 security regression coverage.
- [ ] Frontend tests, typecheck, lint, and production build pass.
- [ ] Ruff, mypy, Bandit, dependency audit, secret scan, forbidden-execution scan, and OpenAPI route check pass.
- [ ] Complete ShopFlow workflow check passes.
- [ ] Public-release audit found no secrets, credentials, private URLs, local paths, debug code, generated build files, or accidental environment files.
- [ ] Branch and commit are recorded: `arena/01a0dd8e-nexora-one`, `[ADD VERIFIED COMMIT SHA]`.

## Limitations to disclose

NEXORA ONE is a reference implementation for a hackathon demonstration, not a production-readiness claim. The repository uses reference authentication, an in-memory repository, local in-memory rate limiting, and local hash-chain storage. ShopFlow mutating actions are controlled simulator operations. Real enterprise adapters, durable persistence, centralized audit retention, a production identity provider, distributed rate limiting, and deployment operations are not included. Provider availability and model identifiers vary by runtime configuration.

If live credentials are unavailable, use this exact statement:

> Live provider verification not executed because no valid runtime credential was available in the environment.

## Final submission links

- Repository: `[ADD VERIFIED REPOSITORY URL]`
- Demo: `[ADD VERIFIED DEMO URL]`
- Video: `[ADD VERIFIED VIDEO URL]`
- Documentation: `[ADD VERIFIED DOCUMENTATION URL OR REPOSITORY PATH]`
- Additional material: `[ADD VERIFIED LINK OR WRITE NONE]`
