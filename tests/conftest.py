"""
Root-suite pytest configuration - sets sys.path and environment variables
BEFORE any test imports (mirrors apps/api/tests/conftest.py).

Root tests import both `apps.api.main` (needs repo root on sys.path) and
`app.core.config` (needs apps/api on sys.path). Env vars must be set before
those imports: Settings() is instantiated at import time and its validators
fail fast without them. ENVIRONMENT=test disables the JWT_SECRET
forbidden-words check; keys deliberately avoid the word "secret" so they
also pass validation if ENVIRONMENT ever ends up non-test.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_ROOT = os.path.join(_REPO_ROOT, "apps", "api")
for _path in (_REPO_ROOT, _API_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("SECRET_KEY", "test-signing-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-hmac-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_ci_default")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_ci_default")
# Keep source grounding OFF so no test hits live Crossref/OpenAlex
# (same guard and rationale as apps/api/tests/conftest.py).
os.environ.setdefault("SOURCE_GROUNDING_ENABLED", "false")
os.environ.setdefault("GROUNDING_GATE_ENABLED", "false")
