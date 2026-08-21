"""Self-signup must stay closed (founder decision 2026-08-21).

Until today the magic-link endpoint created an account for any unknown email
and — with SMTP unset — returned the working login link in the response body.
That combination let anyone with the URL open an account, and anyone who knew
an existing address sign in as that account. These tests pin both halves shut.
"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.auth import MagicLinkToken, User
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_unknown_email_does_not_create_an_account(db_session, monkeypatch):
    """Registration closed: an unknown email gets no account and no link."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    service = AuthService(db_session)

    result = await service.send_magic_link("stranger@example.com")

    user = (
        await db_session.execute(
            select(User).where(User.email == "stranger@example.com")
        )
    ).scalar_one_or_none()
    assert user is None

    token = (
        await db_session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "stranger@example.com")
        )
    ).scalar_one_or_none()
    assert token is None

    assert result["magic_link"] is None


@pytest.mark.asyncio
async def test_closed_registration_does_not_reveal_who_has_an_account(
    db_session, monkeypatch
):
    """The refusal is silent: same shape as the success path, no enumeration."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    db_session.add(User(email="manager1@example.com"))
    await db_session.commit()
    service = AuthService(db_session)

    known = await service.send_magic_link("manager1@example.com")
    unknown = await service.send_magic_link("stranger@example.com")

    assert known["message"] == unknown["message"]
    assert known["expires_in"] == unknown["expires_in"]
    assert known.keys() == unknown.keys()


@pytest.mark.asyncio
async def test_existing_users_can_still_request_a_link(db_session, monkeypatch):
    """Closing signup must not lock out accounts that already exist."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    db_session.add(User(email="manager2@example.com"))
    await db_session.commit()
    service = AuthService(db_session)

    await service.send_magic_link("manager2@example.com")

    token = (
        await db_session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == "manager2@example.com")
        )
    ).scalar_one_or_none()
    assert token is not None


@pytest.mark.asyncio
async def test_registration_can_be_reopened_deliberately(db_session, monkeypatch):
    """The old behaviour stays available, but only as an explicit opt-in."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    service = AuthService(db_session)

    await service.send_magic_link("invited@example.com")

    user = (
        await db_session.execute(
            select(User).where(User.email == "invited@example.com")
        )
    ).scalar_one_or_none()
    assert user is not None


@pytest.mark.asyncio
async def test_login_link_is_never_echoed_outside_debug(db_session, monkeypatch):
    """No SMTP is not a reason to hand the caller a working login link."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", False)
    service = AuthService(db_session)

    result = await service.send_magic_link("nosmtp@example.com")

    assert result["magic_link"] is None
