import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import TypeVar

import structlog

log = structlog.stdlib.get_logger("ai_service.infra.circuit_breaker")
T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Raised when circuit breaker is OPEN and rejects execution."""


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreakerSettings:
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_success_threshold: int = 2


class AsyncCircuitBreaker:
    def __init__(self, name: str, settings: CircuitBreakerSettings) -> None:
        self.name = name
        self._settings = settings
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    async def call(self, fn: Callable[[], Awaitable[T]], *, operation: str) -> T:
        if not self._settings.enabled:
            return await fn()

        await self._before_call(operation)
        try:
            result = await fn()
        except Exception:
            await self._on_failure(operation)
            raise
        await self._on_success(operation)
        return result

    async def _before_call(self, operation: str) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed < self._settings.recovery_timeout_seconds:
                    raise CircuitBreakerOpenError(f"circuit '{self.name}' is OPEN for operation '{operation}'")
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                log.warning(
                    "circuit breaker moved to HALF_OPEN",
                    circuit=self.name,
                    operation=operation,
                )

    async def _on_success(self, operation: str) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._settings.half_open_success_threshold:
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._half_open_successes = 0
                    self._opened_at = 0.0
                    log.info(
                        "circuit breaker CLOSED after recovery",
                        circuit=self.name,
                        operation=operation,
                    )
            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0

    async def _on_failure(self, operation: str) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._trip_open(operation)
                return

            if self._state == CircuitState.CLOSED:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._settings.failure_threshold:
                    self._trip_open(operation)

    def _trip_open(self, operation: str) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._consecutive_failures = 0
        self._half_open_successes = 0
        log.warning(
            "circuit breaker OPENED",
            circuit=self.name,
            operation=operation,
            recovery_timeout_seconds=self._settings.recovery_timeout_seconds,
        )


_REGISTRY_LOCK = Lock()
_REGISTRY: dict[str, AsyncCircuitBreaker] = {}


def get_or_create_circuit_breaker(name: str, settings: CircuitBreakerSettings) -> AsyncCircuitBreaker:
    with _REGISTRY_LOCK:
        breaker = _REGISTRY.get(name)
        if breaker is not None:
            return breaker
        breaker = AsyncCircuitBreaker(name=name, settings=settings)
        _REGISTRY[name] = breaker
        return breaker
