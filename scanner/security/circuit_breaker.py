"""Circuit Breaker - Prevent cascading failures."""

import asyncio
import enum
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation.

    State transitions:
    - CLOSED -> OPEN: When failure threshold exceeded
    - OPEN -> HALF_OPEN: After recovery timeout
    - HALF_OPEN -> CLOSED: On success
    - HALF_OPEN -> OPEN: On failure
    """

    name: str = "default"
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    success_threshold: int = 3  # successes needed in half-open

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self._state == CircuitState.HALF_OPEN

    async def can_execute(self) -> bool:
        """
        Check if execution is allowed.

        Returns:
            True if request should be allowed
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            # HALF_OPEN - allow limited requests
            return True

    async def record_success(self) -> None:
        """Record a successful execution."""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    async def record_failure(self) -> None:
        """Record a failed execution."""
        async with self._lock:
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open -> back to open
                self._transition_to(CircuitState.OPEN)
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    async def execute[T](
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Re-raises any exception from func
        """
        if not await self.can_execute():
            raise CircuitBreakerError(
                f"Circuit '{self.name}' is open"
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self.record_success()
            return result

        except Exception:
            await self.record_failure()
            raise

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0

        logger.info(
            f"Circuit '{self.name}' transitioned: {old_state.value} -> {new_state.value}"
        )

    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        async with self._lock:
            self._transition_to(CircuitState.CLOSED)

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerError(Exception):
    """Exception raised when circuit is open."""

    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        name: str,
        **kwargs: Any,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name=name, **kwargs)
            return self._breakers[name]

    async def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }


# Global registry
circuit_registry = CircuitBreakerRegistry()
