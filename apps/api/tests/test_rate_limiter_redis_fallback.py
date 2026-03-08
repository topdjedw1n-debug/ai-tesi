"""
Test rate limiter graceful fallback when Redis is unavailable.
Tests the defense-in-depth approach to handling Redis connection errors.
"""

import os
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from main import app


class TestRedisUnavailableFallback:
    """Test that rate limiter falls back to memory when Redis unavailable."""

    @pytest.mark.skipif(
        os.environ.get("DISABLE_RATE_LIMIT", "false").lower() == "true",
        reason="Rate limiting is disabled in test environment",
    )
    @pytest.mark.asyncio
    async def test_redis_connection_error_falls_back_to_memory(self):
        """
        Test that when Redis connection fails, the rate limiter gracefully
        falls back to memory-based limiting without crashing.

        This tests Layer 1 (exception handler) and Layer 2 (graceful degradation).
        """
        # Mock Redis connection to raise ConnectionError
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis.side_effect = ConnectionError("Redis connection refused")

            async with AsyncClient(app=app, base_url="http://test") as client:
                # Should NOT crash with AttributeError
                response = await client.get("/health")

                # Should return 200 (health endpoint works)
                assert response.status_code == 200
                assert response.json()["status"] == "healthy"

    @pytest.mark.skipif(
        os.environ.get("DISABLE_RATE_LIMIT", "false").lower() == "true",
        reason="Rate limiting is disabled in test environment",
    )
    @pytest.mark.asyncio
    async def test_multiple_requests_work_with_memory_fallback(self):
        """
        Test that multiple requests work correctly when using memory-based
        rate limiting (Redis unavailable).
        """
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis.side_effect = ConnectionError("Redis unavailable")

            async with AsyncClient(app=app, base_url="http://test") as client:
                # Make 10 requests - all should succeed (memory limiter works)
                for i in range(10):
                    response = await client.get("/health")
                    assert response.status_code == 200, f"Request {i} failed"

    @pytest.mark.skipif(
        os.environ.get("DISABLE_RATE_LIMIT", "false").lower() == "true",
        reason="Rate limiting is disabled in test environment",
    )
    @pytest.mark.asyncio
    async def test_no_attribute_error_on_connection_error(self):
        """
        Regression test: Ensure we don't get AttributeError when trying to
        access .detail on ConnectionError exception.

        This was the original bug - SlowAPI's default handler expected
        RateLimitExceeded.detail but got ConnectionError instead.
        """
        with patch("redis.asyncio.from_url") as mock_redis:
            # Simulate Redis connection failure
            mock_redis.side_effect = ConnectionError("Connection refused")

            async with AsyncClient(app=app, base_url="http://test") as client:
                try:
                    response = await client.get("/health")
                    # Should NOT raise AttributeError
                    assert response.status_code in [
                        200,
                        503,
                    ]  # Either works or service unavailable
                except AttributeError as e:
                    if "'ConnectionError' object has no attribute 'detail'" in str(e):
                        pytest.fail(
                            "Bug not fixed: Still getting AttributeError on ConnectionError"
                        )
                    raise  # Re-raise if different AttributeError
