"""Regression coverage for the manager/admin password-login boundary."""

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from starlette.requests import Request

from app.api.v1.endpoints import auth as auth_endpoints
from app.core.exceptions import AuthenticationError, RateLimitError
from app.models.auth import User
from app.services.auth_service import AuthService


def _request(ip: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/auth/admin-login",
            "raw_path": b"/api/v1/auth/admin-login",
            "query_string": b"",
            "headers": [(b"x-request-id", b"admin-login-test")],
            "client": (ip, 443),
            "server": ("testserver", 443),
        }
    )


@pytest.mark.asyncio
async def test_five_bad_admin_passwords_lock_the_next_attempt(db_session, monkeypatch):
    admin = User(
        email="admin-lockout@example.com",
        full_name="Admin Lockout",
        password_hash=AuthService.hash_password("correct-password"),
        is_active=True,
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()

    state = {"failures": 0}

    async def check_lockout(_identifier):
        if state["failures"] >= 5:
            return timedelta(minutes=15)
        return None

    async def record_failure(_identifier):
        state["failures"] += 1

    monkeypatch.setattr(auth_endpoints, "check_auth_lockout", check_lockout)
    monkeypatch.setattr(auth_endpoints, "record_auth_failure", record_failure)
    monkeypatch.setattr(auth_endpoints, "clear_auth_failures", _no_op)
    monkeypatch.setattr(auth_endpoints, "log_security_audit_event", lambda **_: None)

    handler = getattr(
        auth_endpoints.admin_simple_login,
        "__wrapped__",
        auth_endpoints.admin_simple_login,
    )
    bad_login = auth_endpoints.AdminLoginRequest(
        email=admin.email, password="wrong-password"
    )
    for _ in range(5):
        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await handler(request=_request(), login_data=bad_login, db=db_session)

    assert state["failures"] == 5
    correct_login = auth_endpoints.AdminLoginRequest(
        email=admin.email, password="correct-password"
    )
    with pytest.raises(RateLimitError, match="temporarily locked"):
        await handler(request=_request(), login_data=correct_login, db=db_session)


async def _no_op(*_args, **_kwargs):
    return None


RATE_LIMIT_PROBE = r"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient

from app.core.exceptions import AuthenticationError
from app.middleware import rate_limit as rate_limit_module
from app.api.v1.endpoints import auth as auth_endpoints


async def override_db():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    yield db


async def main():
    app = FastAPI()
    rate_limit_module.setup_rate_limiter(app)
    app.include_router(auth_endpoints.router, prefix="/api/v1/auth")
    app.dependency_overrides[auth_endpoints.get_db] = override_db

    @app.exception_handler(AuthenticationError)
    async def authentication_error(_request: Request, exc: AuthenticationError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async with AsyncClient(app=app, base_url="http://test") as client:
        statuses = []
        for _ in range(6):
            response = await client.post(
                "/api/v1/auth/admin-login",
                json={"email": "missing-admin@example.com", "password": "wrong"},
            )
            statuses.append(response.status_code)

    assert statuses[:5] == [401] * 5, statuses
    assert statuses[5] == 429, statuses


asyncio.run(main())
"""


def test_sixth_admin_login_request_within_minute_is_rate_limited():
    """A fresh process is required because decorators bind at import time."""
    environment = os.environ.copy()
    environment.update(
        {
            "ENV_FILE": os.devnull,
            "ENVIRONMENT": "test",
            "DISABLE_RATE_LIMIT": "false",
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "REDIS_URL": "redis://127.0.0.1:1/0",
            "SECRET_KEY": "rate-limit-test-secret-key-minimum-32-characters",
            "JWT_SECRET": "rate-limit-test-jwt-secret-minimum-32-characters",
            "CORS_ALLOWED_ORIGINS": "http://test",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", RATE_LIMIT_PROBE],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
