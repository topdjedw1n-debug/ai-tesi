# Wave 1 Release Candidate Changelog

**Tag:** wave1-rc-2026-02-23-01
**Date:** 2026-02-23

## Fixes

1. **Backend logger key conflict** (`apps/api/app/services/background_jobs.py`)
   - Renamed `extra["args"]` to `extra["task_args_snapshot"]` to avoid `KeyError` from Python logging internals.

2. **FE/BE API contract sync** (`apps/web/lib/api.ts`, `apps/web/lib/api/admin.ts`)
   - `GENERATE.FULL`: `/api/v1/generate/full` -> `/api/v1/generate/full-document`
   - `GENERATE.USAGE`: string -> function with userId parameter
   - `PRICING.CONFIG` removed (endpoint does not exist); only `CURRENT` and `CALCULATE` remain
   - Admin `logout`: path corrected to `/api/v1/admin/auth/logout`
   - Admin `blockUser`/`unblockUser`: method changed from POST to PUT; `blockUser` now sends `reason`
   - Admin `makeAdmin`: path corrected to `/make-admin`
   - Admin `bulkUserAction`: payload key changed from `ids` to `user_ids`

3. **Refunds user-side fallback** (`apps/web/lib/api/refunds.ts`)
   - `getRefundRequest` and `listUserRefunds` return safe defaults (`null`/`[]`) since backend user-read endpoints do not exist yet.

4. **Frontend quality gates re-enabled** (`apps/web/next.config.js`)
   - `typescript.ignoreBuildErrors`: `true` -> `false`
   - `eslint.ignoreDuringBuilds`: `true` -> `false`

5. **Web health endpoint** (`apps/web/app/api/health/route.ts`)
   - New: `GET /api/health` returns `{"status":"ok"}` for Docker healthcheck.

6. **Admin logout typing bug** (`apps/api/app/api/v1/endpoints/admin_auth.py`)
   - Return type changed from `dict[str, str]` to `dict[str, Any]` to fix HTTP 500 when `count` (int) failed Pydantic string validation.

7. **Docker compose hardening** (`infra/docker/docker-compose.prod.yml`)
   - Added env fallbacks, web healthcheck uses `wget` on `127.0.0.1` to avoid IPv6 issues.

## New tests

- `apps/api/tests/test_admin_auth_endpoints.py`: 3 regression tests for admin logout (auth required, 200 success, response type validation).

## Gate results

| Gate | Result |
|------|--------|
| backend pytest | 391 passed, 6 skipped, 0 failed |
| web type-check | 0 errors |
| web lint | 0 warnings/errors |
| web jest | 12 suites, 122 passed, 1 skipped |
| web build | compiled, 0 errors |
| runtime smoke (health) | API 200, Web 200 |
| runtime smoke (auth) | user 200, admin 200 |
