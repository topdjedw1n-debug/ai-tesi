"""
Retry strategy with exponential backoff and fallback models
"""
import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class RetryStrategy:
    """
    Retry strategy with exponential backoff and fallback models.
    """

    def __init__(
        self,
        max_retries: int = 5,
        delays: list[int] | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            delays: List of delay seconds for each retry
            circuit_breaker: Optional circuit breaker instance
        """
        self.max_retries = max_retries
        self.delays = delays or [2, 4, 8, 16, 32]
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    # Fallback models for each primary model
    FALLBACK_MODELS = {
        "gpt-4": ["gpt-4-turbo", "gpt-3.5-turbo"],
        "gpt-4-turbo": ["gpt-3.5-turbo"],
        "claude-3-5-sonnet-20241022": ["claude-3-opus-20240229", "gpt-4"],
        "claude-3-opus-20240229": ["claude-3-5-sonnet-20241022"],
    }

    async def execute_with_retry(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Try with circuit breaker
                result = await self.circuit_breaker.call_async(func, *args, **kwargs)

                if attempt > 0:
                    logger.info(f"Success after {attempt + 1} attempts")

                return result

            except CircuitBreakerOpenError as e:
                # Circuit breaker is open - wait and retry
                logger.warning(f"Circuit breaker open (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    delay = self.delays[min(attempt, len(self.delays) - 1)]
                    logger.info(f"Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    last_error = e
                else:
                    raise

            except Exception as e:
                # Track error for logging
                last_error = e

                # Check if we should retry
                if attempt < self.max_retries:
                    delay = self.delays[min(attempt, len(self.delays) - 1)]
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed: "
                        f"{type(e).__name__}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise Exception("Retry exhausted without error")


def with_retry(
    max_retries: int = 5,
    delays: list[int] | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[F], F]:
    """
    Decorator for retry logic with exponential backoff.

    Usage:
        @with_retry(max_retries=3, delays=[1, 2, 4])
        async def my_function():
            ...

    Args:
        max_retries: Maximum number of retry attempts
        delays: List of delay seconds for each retry
        circuit_breaker: Optional circuit breaker instance
    """

    def decorator(func: F) -> F:
        strategy = RetryStrategy(max_retries, delays, circuit_breaker)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await strategy.execute_with_retry(func, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator
