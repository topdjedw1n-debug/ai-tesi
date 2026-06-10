# MASTER Compliance Matrix

**Updated:** 2026-02-23
**Scope:** Operational MASTER compliance (Wave 1 + Wave 3B)

Status taxonomy:
- `Implemented`
- `Disabled by feature flag (temporary)`
- `Deferred (Wave 2+)`

| Feature | MASTER Status | Real Code Status | Gap | Action |
|---|---|---|---|---|
| Canonical FE/BE API contract | Required | Implemented | None | Keep backend as canonical source |
| `POST /api/v1/generate/full-document` | Required | Implemented | None | Covered by contract smoke |
| `GET /api/v1/generate/usage/{user_id}` | Required | Implemented | None | Covered by contract smoke |
| Admin logout/block/unblock/make-admin contracts | Required | Implemented | None | Covered by contract smoke |
| User payment flow (`create-checkout`, verify, history) | Required | Implemented | None | Runtime smoke + manual UI smoke |
| User refund create flow | Required | Implemented | None | Runtime smoke + manual UI smoke |
| User refund read flow (`GET /api/v1/refunds`, `GET /api/v1/refunds/{id}`) | Required for full restore | Implemented | None | Added in Wave 3B |
| Web health endpoint `/api/health` | Required | Implemented | None | Docker healthcheck uses this route |
| API health endpoint `/health` | Required | Implemented | None | Runtime smoke uses this route |
| Strict web gates (`lint`, `type-check`, `jest`, `build`) | Required | Implemented | None | Mandatory CI jobs |
| Mandatory backend gate (`pytest`) | Required | Implemented | None | Mandatory CI job |
| Repo hygiene gate (backup artifacts) | Required | Implemented | None | CI `repo-hygiene` job |
| External RAG APIs (Perplexity/Tavily/Serper) | Optional/To implement | Deferred (Wave 2+) | Expected | Backlog by decision |
| Refund approval/rejection email notifications | Planned improvement | Deferred (Wave 2+) | Expected | Keep TODO in `refund_service.py` |

## Release Scope Lock

In release scope:
- Runtime-stable operational functionality from MASTER.
- Full payment/refund user flows with ownership checks.
- Strict CI and runtime smoke gates.

Out of release scope:
- New external provider integrations for RAG.
- Non-critical product enhancements not required for operational parity.
