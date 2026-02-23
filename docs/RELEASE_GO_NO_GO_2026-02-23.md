# Release Go/No-Go Checklist (23.02.2026)

## Release mode
- Strict Go-Live

## P0 Gates
- [x] backend-pytest local pass
- [x] web lint local pass
- [x] web type-check local pass
- [x] web jest local pass
- [x] web build local pass
- [x] FE/BE contract lock checks added (`apps/web/lib/__tests__/api-contract-smoke.test.ts`)
- [x] Repo hygiene rules tightened (`.gitignore`, CI hygiene job)
- [x] User payment/refund fragile flows disabled with controlled fallback
- [x] Web health endpoint available (`/api/health`)
- [x] Runtime smoke in prod-like Docker environment

## Automated gate results (23.02.2026)

| Gate | Result | Details |
|------|--------|---------|
| backend pytest | PASS | 391 passed, 6 skipped, 0 failed (125s) |
| web type-check | PASS | 0 errors (strict: ignoreBuildErrors=false) |
| web lint | PASS | 0 warnings/errors (strict: ignoreDuringBuilds=false) |
| web jest | PASS | 12 suites, 122 passed, 1 skipped, 0 failed |
| web build | PASS | 26+ pages compiled, 0 errors |
| Docker stack | PASS | 5/5 containers healthy (api, web, postgres, redis, minio) |
| runtime smoke (health) | PASS | API /health 200, Web /api/health 200 |
| runtime smoke (auth) | PASS | /api/v1/auth/me 200, /api/v1/admin/stats 200 |

## Bugs found and fixed during validation

1. **Admin logout typing bug**: `admin_auth.py` endpoint returned `{"count": 0}` (int) but return type was `dict[str, str]`, causing HTTP 500. Fixed return type to `dict[str, Any]`. Regression test added (`test_admin_auth_endpoints.py`).

## Runtime smoke scenarios (prod-like Docker)
1. `GET /health` (API) -> 200
2. `GET /api/health` (Web) -> 200
3. `GET /api/v1/auth/me` (authenticated) -> 200
4. `GET /api/v1/admin/stats` (admin authenticated) -> 200
5. Contract smoke: all Wave 1 fixed endpoints respond without 404/405

## Residual risks
- Manual UI smoke (browser) not yet performed -- see checklist below
- Payment/refund user flows intentionally disabled via feature flags (`NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW=false`, `NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW=false`)

## Decision
- **Status: Go (pending manual UI smoke sign-off)**
- All automated quality gates and runtime smoke pass.
- Final Go requires human verification of browser UI flows (see Manual UI Smoke Checklist below).

---

## Manual UI Smoke Checklist

Instructions: open browser at http://localhost:3000, perform each scenario, record Pass/Fail.

| # | Scenario | Steps | Expected outcome | Pass/Fail |
|---|----------|-------|------------------|-----------|
| 1 | User login | Go to /auth/login, enter valid email, follow magic link flow | Redirect to /dashboard, user sees dashboard | |
| 2 | User dashboard | After login, check /dashboard | Page loads without JS errors, stats/documents shown | |
| 3 | User logout | Click logout button | Redirect to /auth/login, tokens cleared | |
| 4 | Admin login | Go to /admin/login, enter admin credentials | Redirect to /admin/dashboard | |
| 5 | Admin dashboard | After admin login, check /admin/dashboard | Stats, charts, activity load without errors | |
| 6 | Admin logout | Click admin logout | Redirect to /admin/login, session cleared | |
| 7 | Admin: block user | Go to /admin/users, select user, click Block | User status changes to blocked, confirmation shown | |
| 8 | Admin: unblock user | Select blocked user, click Unblock | User status changes to active | |
| 9 | Admin: make admin | Select user, click Make Admin | User role updated, confirmation shown | |
| 10 | Payment flow (disabled) | Navigate to payment page | Controlled disabled UI or redirect, no crash | |
| 11 | Refund flow (disabled) | Navigate to refund page | Fallback message shown, no crash or undefined errors | |

**Sign-off:** _________________ **Date:** _________________
