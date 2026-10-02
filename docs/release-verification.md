# Phase 10 release verification record

This record belongs to the reference checkout and contains no provider credential. Provider verification is performed by `scripts/verify_nebius_runtime.py` through the existing `POST /api/ai/test` route, `AIService`, and `NebiusNemotronProvider`.

## Runtime observed in this checkout

| Check | Observed result |
| --- | --- |
| Provider | Nebius Token Factory / NVIDIA Nemotron integration |
| Configured base URL | Not configured in the verification environment; no URL was printed from a secret or local file |
| Configured model | Not configured in the verification environment |
| Runtime status | `NOT_EXECUTED` because the required runtime credential/configuration was absent |
| Structured response validation | Not executed against a live provider; server validation is covered by AI tests and the safe verification route |
| Evidence grounding | Not executed against a live provider; server evidence-index grounding is covered by provider/service tests |
| Registered action/tool validation | Server-side validation is retained and regression-tested; no model output is treated as executable authority |
| Timeout handling | Bounded timeout and transient retry behavior retained; no live timeout was induced in this environment |
| Safe provider failure | Verified through the unconfigured AI route and complete ShopFlow demo; no secret appears in the response or activity |
| Secret output | None |

The exact runtime limitation is:

> Live provider verification not executed because no valid runtime credential was available in the environment.

A configured run must replace only the runtime result fields above with the actual output of the verification script. It must record the configured base URL and model without recording `NEBIUS_API_KEY`. A successful status is valid only after an actual HTTP request returns a structured response that passes the existing `AIService` and provider validation path.

## Controlled ShopFlow verification

`scripts/run_shopflow_demo.py` completed the `payment-failure` workflow with:

- `SIMULATED / CONTROLLED DEMONSTRATION` evidence and impact context;
- investigation and provenance-bound evidence;
- AI assistance represented as a verified response or an explicit safe provider failure;
- server-validated recommendation and registered action;
- separate human approval;
- controlled simulator execution;
- verification proof before resolution;
- generated incident report; and
- hash-chained action audit.

The failure-path regression suite also covers verification failure, rollback, bounded retry, permanent failure, and `REQUIRES_HUMAN` escalation. No production readiness claim is made: authentication, persistence, rate limiting, audit storage, and enterprise adapters remain reference/in-memory or simulator boundaries.
