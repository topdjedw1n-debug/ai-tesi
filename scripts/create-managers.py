#!/usr/bin/env python3
"""
Create/refresh manager login accounts (username + password, no email needed).

Managers are just regular users that have a password set. The "login" is stored
verbatim in ``User.email`` and matched by ``POST /api/v1/auth/login``, so plain
logins such as ``manager1`` work without any real mailbox.

Usage:
    python scripts/create-managers.py            # creates manager1..manager5
    python scripts/create-managers.py 3          # creates manager1..manager3
    python scripts/create-managers.py alice bob  # creates logins 'alice', 'bob'

Each account is created with:
  - login (email column) = the given name
  - is_active=True, is_verified=True, is_admin=False, preferred_language='it'
  - a freshly generated strong password (printed once, save it)

Re-running updates the password of existing accounts (idempotent).
"""

import asyncio
import secrets
import sys
from pathlib import Path

# Add the API app to the import path
project_root = Path(__file__).parent.parent / "apps" / "api"
sys.path.insert(0, str(project_root))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

# Unambiguous alphabet (no 0/O/1/l/I) so passwords are easy to read & type
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def resolve_logins(args: list[str]) -> list[str]:
    if len(args) == 1 and args[0].isdigit():
        return [f"manager{i}" for i in range(1, int(args[0]) + 1)]
    if args:
        return args
    return [f"manager{i}" for i in range(1, 6)]


async def upsert_manager(db, login: str, password: str) -> str:
    result = await db.execute(select(User).where(User.email == login))
    user = result.scalar_one_or_none()
    password_hash = AuthService.hash_password(password)

    if user:
        user.password_hash = password_hash
        user.is_active = True
        user.is_verified = True
        return "updated"

    db.add(
        User(
            email=login,
            full_name=login.capitalize(),
            password_hash=password_hash,
            is_active=True,
            is_verified=True,
            is_admin=False,
            preferred_language="it",
        )
    )
    return "created"


async def main() -> None:
    logins = resolve_logins(sys.argv[1:])

    creds: list[tuple[str, str, str]] = []
    async with AsyncSessionLocal() as db:
        for login in logins:
            password = generate_password()
            action = await upsert_manager(db, login, password)
            creds.append((login, password, action))
        await db.commit()

    print("=" * 56)
    print(f"{'LOGIN':<16}{'PASSWORD':<20}STATUS")
    print("-" * 56)
    for login, password, action in creds:
        print(f"{login:<16}{password:<20}{action}")
    print("=" * 56)
    print("Sign in at: <frontend-url>/auth/login  (login + password)")
    print("Language is preset to Italian. Passwords are shown once — save them.")


if __name__ == "__main__":
    asyncio.run(main())
