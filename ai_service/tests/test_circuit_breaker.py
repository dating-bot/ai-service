import asyncio

import pytest

from ai_service.infra.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerSettings,
)


@pytest.mark.asyncio
async def test_breaker_opens_after_failures_and_then_recovers() -> None:
    breaker = AsyncCircuitBreaker(
        "test-breaker",
        CircuitBreakerSettings(
            enabled=True,
            failure_threshold=2,
            recovery_timeout_seconds=0.05,
            half_open_success_threshold=2,
        ),
    )

    async def _fail() -> int:
        msg = "boom"
        raise RuntimeError(msg)

    async def _ok() -> int:
        return 1

    with pytest.raises(RuntimeError):
        await breaker.call(_fail, operation="x")
    with pytest.raises(RuntimeError):
        await breaker.call(_fail, operation="x")

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(_ok, operation="x")

    await asyncio.sleep(0.06)
    assert await breaker.call(_ok, operation="x") == 1
    assert await breaker.call(_ok, operation="x") == 1


@pytest.mark.asyncio
async def test_breaker_disabled_never_opens() -> None:
    breaker = AsyncCircuitBreaker(
        "test-breaker-disabled",
        CircuitBreakerSettings(
            enabled=False,
            failure_threshold=1,
            recovery_timeout_seconds=1.0,
            half_open_success_threshold=1,
        ),
    )

    async def _ok() -> int:
        return 42

    assert await breaker.call(_ok, operation="x") == 42
