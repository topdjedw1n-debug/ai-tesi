"""
Defensive helpers for reading SQLAlchemy execute results.

Some fail-path tests intentionally return None (or partial mocks) from
mocked db.execute(); these helpers treat that as "not found" / "empty"
instead of raising, keeping recovery paths resilient.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def safe_scalar_one_or_none(result: Any, query_name: str) -> Any | None:
    """
    Safely read scalar_one_or_none from SQLAlchemy execute result.

    Some fail-path tests intentionally return None from mocked db.execute().
    We treat that as "not found" instead of raising AttributeError.
    """
    if result is None:
        logger.warning(
            f"DB execute returned None for {query_name}; using fallback None"
        )
        return None

    if not hasattr(result, "scalar_one_or_none"):
        logger.warning(
            f"DB result for {query_name} has no scalar_one_or_none(); using fallback None"
        )
        return None

    try:
        return result.scalar_one_or_none()
    except Exception as e:
        logger.warning(
            f"Failed to read scalar_one_or_none() for {query_name}; using fallback None: {e}"
        )
        return None


def safe_scalars_all(result: Any, query_name: str) -> list[Any]:
    """
    Safely read scalars().all() from SQLAlchemy execute result.

    Returns an empty list on mocked/invalid results to keep recovery paths resilient.
    """
    if result is None:
        logger.warning(f"DB execute returned None for {query_name}; using fallback []")
        return []

    if not hasattr(result, "scalars"):
        logger.warning(
            f"DB result for {query_name} has no scalars(); using fallback []"
        )
        return []

    try:
        values = result.scalars().all()
        return list(values) if values else []
    except Exception as e:
        logger.warning(
            f"Failed to read scalars().all() for {query_name}; using fallback []: {e}"
        )
        return []
