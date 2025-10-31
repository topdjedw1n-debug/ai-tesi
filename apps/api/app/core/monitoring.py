"""
Monitoring and error tracking (Sentry) initialization.
Prometheus metrics export.
"""

from typing import TYPE_CHECKING

import sentry_sdk
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

if TYPE_CHECKING:
    from fastapi import FastAPI


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


def setup_prometheus(app: "FastAPI", environment: str) -> None:
    """Setup Prometheus metrics collection and export endpoint."""
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/redoc", "/openapi.json"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")

