"""
Circuit Breaker pattern implementation for resilient AI service calls
"""
import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.

    Prevents cascading failures by opening circuit after threshold failures.
    Automatically attempts recovery after timeout.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] | tuple[type[Exception], ...] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception types to count as failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = CircuitState.CLOSED

        self._lock = asyncio.Lock()

    async def call_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Call async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If function call fails
        """
        async with self._lock:
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info("Attempting to close circuit breaker (HALF_OPEN state)")
                    self.state = CircuitState.HALF_OPEN
                else:
                    wait_seconds = (
                        self.recovery_timeout
                        - (datetime.now() - self.last_failure_time).total_seconds()
                    )  # type: ignore
                    logger.warning(
                        f"Circuit breaker is OPEN. Waiting {wait_seconds:.1f}s before retry"
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is open. Wait {wait_seconds:.1f}s before retry"
                    )

            # Attempt to call function
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure(e)
                raise

    def _on_success(self) -> None:
        """Handle successful call"""
        if self.state != CircuitState.CLOSED:
            logger.info(f"Circuit breaker recovered: {self.state.value} -> CLOSED")

        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self, error: Exception) -> None:
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        logger.warning(
            f"Circuit breaker failure count: {self.failure_count}/{self.failure_threshold}. "
            f"Error: {type(error).__name__}"
        )

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Will retry in {self.recovery_timeout}s"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state.value

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state"""
        logger.info("Circuit breaker manually reset")
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""

    pass

