# Release Go/No-Go Checklist (Updated 24.02.2026)

## Release mode
- Strict Go-Live

## Scope lock for this cycle (24.02.2026)
- Strategy: continue in current branch with explicit file allowlist (no `git add .`).
- Included in scope:
  - `apps/api/app/api/v1/endpoints/documents.py`
  - `apps/api/tests/test_documents_stats_endpoint.py`
  - `apps/web/lib/api/admin.ts`
  - `apps/web/components/admin/users/UsersTable.tsx`
  - `apps/web/components/admin/users/UserDetails.tsx`
  - `apps/web/__tests__/components/admin/UsersTable.test.tsx`
  - `apps/web/e2e/smoke-preprod.spec.ts` (type-check fix only)
  - `apps/web/app/layout.tsx`
  - `apps/web/public/favicon.ico`
  - `apps/web/public/manifest.json`
  - `docs/RELEASE_GO_NO_GO_2026-02-23.md`
  - `docs/MVP_PLAN.md`
  - `docs/sec/DECISIONS_LOG.md`
- Excluded from scope:
  - all unrelated modified/untracked files in dirty working tree;
  - payment/refund manual browser smoke scenarios for this cycle (explicitly skipped by scope decision).

## P1 defects fixed in this cycle
1. `GET /api/v1/documents/stats` returned `422` due route order.
   - Fix: move static route `/stats` before dynamic `/{document_id}` in `documents.py`.
   - Regression tests added in `test_documents_stats_endpoint.py`.
2. Admin Users UI had no visible Block/Unblock actions.
   - Fix: normalize backend user payload in `adminApiClient` with canonical `is_active`.
   - Fix: action rendering in `UsersTable` and `UserDetails` now uses normalized status with `is_active` fallback.
   - Regression tests extended in `UsersTable.test.tsx`.

## P2 cleanup completed
- Added `apps/web/public/favicon.ico` and `apps/web/public/manifest.json` to remove browser 404 noise.
- Added metadata links in `apps/web/app/layout.tsx`.
- `307` redirect on `/api/v1/documents` is kept as technical debt (non-blocking).

## Automated gate results (24.02.2026)

| Gate | Result | Details |
|------|--------|---------|
| backend pytest | PASS | 396 passed, 6 skipped, 0 failed |
| web lint | PASS | 0 warnings/errors |
| web type-check | PASS | 0 errors |
| web jest | PASS | 12 suites, 125 passed, 1 skipped, 0 failed |
| web build | PASS | 27 pages compiled, 0 errors |

## Runtime smoke (24.02.2026)

Host script status:
- `scripts/runtime_smoke.sh` from sandbox host -> blocked by localhost access (`000`), known sandbox limitation.

Container-internal authenticated checks:
1. `GET /health` -> 200
2. `GET /api/v1/auth/me` -> 200
3. `GET /api/v1/payment/history` -> 200
4. `GET /api/v1/refunds` -> 200
5. `POST /api/v1/generate/full-document` -> 422 (expected validation)
6. `GET /api/v1/admin/stats` -> 200
7. `PUT /api/v1/admin/users/999999/block` -> 400 (valid route, expected validation)
8. `PUT /api/v1/admin/users/999999/unblock` -> 400 (valid route, expected validation)
9. `POST /api/v1/admin/users/999999/make-admin` -> 400 (valid route, expected validation)
10. `POST /api/v1/admin/auth/logout` -> 200

Web container check:
- `GET /api/health` -> 200 (`{"status":"ok"}`)

## Manual UI smoke status
- Browser smoke cannot be executed from this sandbox due Playwright webServer bind restriction (`EPERM` on port 3000).
- Required outside sandbox by operator:
  - `/dashboard` stats render check
  - `/admin/users` Block/Unblock visibility + actions
  - `/admin/users/[id]` Block/Unblock + make-admin
- Payment/refund UI smoke for this cycle: **SKIPPED by scope decision**.

## Residual risks
- Pre-prod still has Stripe live keys in local env (`apps/api/.env`, `apps/web/.env.local`).
  - Risk: real charges during manual payment tests.
  - Recommendation: switch pre-prod smoke to Stripe test keys before strict final sign-off.

## Decision
- **Status: Conditional Go**
- Rationale:
  - All code and contract quality gates are green.
  - P1 defects from manual smoke are fixed and covered by regression tests.
  - Payment/refund UI smoke intentionally skipped by scope decision.
  - Final strict Go requires external manual browser sign-off and Stripe pre-prod risk acknowledgement.
