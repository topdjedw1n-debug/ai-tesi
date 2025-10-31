# Quality Gate Policy (SSOT)

## Phase 1.2 Pass Criteria

### P0 Requirements (Blocking)

- [x] Python 3.11 enforced in Dev/Docker/CI
- [x] Ruff = 0 errors
- [x] Pytest smoke: ≥3 tests PASS (health, auth, rate_limit)
- [x] Runtime: /health → 200 OK in Docker
- [x] MyPy: 0 blocking errors (warnings allowed)

### P1 Requirements (Recommended)

- [x] Node.js ≥18.17.0 enforced
- [x] CI gates active (Python version, Ruff, MyPy, Tests, Runtime)
- [x] Artifacts uploaded (pytest-report.txt, mypy.txt, health-log.txt)

### Gate Status: **PASS** ✅

## Implementation Details

### Python 3.11 Enforcement
- Dockerfile: `FROM python:3.11-slim`
- pyproject.toml: `requires-python = ">=3.11"`
- CI: `python-version: "3.11"` with version gate check

### Ruff Linting
- Configuration: `pyproject.toml` with target-version = "py311"
- CI Gate: `ruff check . --output-format=github`
- Status: 0 errors (verified in Phase 1.1)

### Pytest Smoke Tests
- Location: `apps/api/tests/`
- Tests:
  - `test_health_endpoint.py`: GET /health → 200 OK
  - `test_auth_no_token.py`: GET /api/v1/auth/me without token → 401
  - `test_rate_limit_init.py`: App starts, rate limiter initializes
- CI Command: `pytest tests -q -m "not integration" --maxfail=3`

### Runtime Health Check
- Docker Compose: `docker-compose.test.yml`
- Endpoint: GET /health → 200 OK
- Log Check: No errors in runtime logs

### MyPy Type Checking
- Configuration: `mypy.ini` with strict settings
- Target: 0 blocking errors (warnings allowed)
- Fixed: Added type annotation for `setup_prometheus(app: "FastAPI", ...)`

### Node.js Version Gate
- File: `apps/web/.nvmrc` → `18.17.0`
- CI Check: Validates Node.js ≥18.17

## CI Workflow

Location: `.github/workflows/ci.yml`

Jobs:
1. **python-quality-gate**: Python 3.11, Ruff, MyPy, Pytest
2. **runtime-smoke-test**: Docker compose + /health endpoint
3. **node-version-gate**: Node.js version validation

Artifacts:
- `ruff-report.txt`
- `mypy.txt`
- `pytest-report.txt`
- `health-log.txt`
- `runtime-logs.txt`
- `node-version.txt`

## Next Steps

After Phase 1.2 PASS:
- Phase 2: MyPy remediation (reduce warnings to ≤40)
- Phase 3: Additional quality improvements

