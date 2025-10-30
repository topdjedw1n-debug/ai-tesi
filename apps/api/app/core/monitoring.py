"""
Monitoring and error tracking (Sentry) initialization.
"""

import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def setup_sentry(environment: str, dsn: str | None) -> None:
    """Initialize Sentry with FastAPI and SQLAlchemy integrations if DSN provided."""
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        environment=environment,
        traces_sample_rate=0.2,
        profiles_sample_rate=0.2,
        send_default_pii=False,
    )


