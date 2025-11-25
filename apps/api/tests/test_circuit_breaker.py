"""
Tests for Circuit Breaker and Retry Strategy
"""
import pytest

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.services.retry_strategy import RetryStrategy


@pytest.mark.asyncio
async def test_circuit_breaker_closed():
    """Test circuit breaker in CLOSED state"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    # Successful call
    async def success():
        return "success"

    result = await breaker.call_async(success)
    assert result == "success"
    assert breaker.get_state() == "closed"


@pytest.mark.asyncio
async def test_circuit_breaker_open():
    """Test circuit breaker opening after failures"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    # Fail multiple times
    async def fail():
        raise ValueError("test error")

    # First 2 failures should pass through
    for _ in range(2):
        with pytest.raises(ValueError):
            await breaker.call_async(fail)

    # After threshold failures, circuit should open
    with pytest.raises(ValueError):
        await breaker.call_async(fail)

    # Next call should raise CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call_async(fail)

    assert breaker.get_state() == "open"


@pytest.mark.asyncio
async def test_circuit_breaker_manual_reset():
    """Test manual circuit breaker reset"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    # Fail to open circuit
    async def fail():
        raise ValueError("test")

    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call_async(fail)

    assert breaker.get_state() == "open"

    # Manually reset
    breaker.reset()
    assert breaker.get_state() == "closed"

    # Should work again
    async def success():
        return "success"

    result = await breaker.call_async(success)
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_strategy_success():
    """Test retry strategy with successful call"""
    strategy = RetryStrategy(max_retries=3, delays=[0.1, 0.1])

    async def success():
        return "success"

    result = await strategy.execute_with_retry(success)
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_strategy_with_failures():
    """Test retry strategy with transient failures"""
    strategy = RetryStrategy(max_retries=3, delays=[0.1, 0.1])

    call_count = 0

    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient error")
        return "success"

    result = await strategy.execute_with_retry(fail_then_succeed)
    assert result == "success"
    assert call_count == 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_retry_strategy_exhausted():
    """Test retry strategy exhaustion"""
    strategy = RetryStrategy(max_retries=2, delays=[0.1, 0.1])

    async def always_fail():
        raise ValueError("always fails")

    with pytest.raises(ValueError):
        await strategy.execute_with_retry(always_fail)


@pytest.mark.asyncio
async def test_retry_with_circuit_breaker():
    """Test retry strategy with circuit breaker integration"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
    strategy = RetryStrategy(max_retries=5, delays=[0.1, 0.1], circuit_breaker=breaker)

    call_count = 0

    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient error")
        return "success"

    result = await strategy.execute_with_retry(fail_then_succeed)
    assert result == "success"
    assert call_count == 3
