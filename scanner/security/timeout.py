"""Timeout Controller - Request timeout management."""

import asyncio
from dataclasses import dataclass
from typing import Any

from common.constants import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_TOTAL_TIMEOUT,
)


@dataclass
class TimeoutConfig:
    """Timeout configuration."""

    connect: float = DEFAULT_CONNECT_TIMEOUT  # Connection timeout in seconds
    read: float = DEFAULT_READ_TIMEOUT  # Read timeout in seconds
    total: float = DEFAULT_TOTAL_TIMEOUT  # Total operation timeout in seconds

    def to_httpx_timeout(self) -> dict[str, float]:
        """Convert to httpx timeout format."""
        return {
            "connect": self.connect,
            "read": self.read,
            "write": self.read,  # Use read timeout for write
            "pool": self.connect,
        }


class TimeoutController:
    """
    Timeout controller for managing operation timeouts.

    Supports:
    - Connection timeout
    - Read timeout
    - Total operation timeout
    - Custom timeout per operation
    """

    def __init__(
        self,
        default_config: TimeoutConfig | None = None,
    ) -> None:
        """
        Initialize timeout controller.

        Args:
            default_config: Default timeout configuration
        """
        self._default_config = default_config or TimeoutConfig()
        self._custom_timeouts: dict[str, TimeoutConfig] = {}

    def set_timeout(self, key: str, config: TimeoutConfig) -> None:
        """Set custom timeout for a key."""
        self._custom_timeouts[key] = config

    def get_timeout(self, key: str | None = None) -> TimeoutConfig:
        """Get timeout configuration for a key."""
        if key and key in self._custom_timeouts:
            return self._custom_timeouts[key]
        return self._default_config

    def clear_timeout(self, key: str) -> None:
        """Clear custom timeout for a key."""
        self._custom_timeouts.pop(key, None)

    async def execute_with_timeout[T](
        self,
        coro: Any,
        timeout: float | None = None,
        key: str | None = None,
    ) -> T:
        """
        Execute a coroutine with timeout.

        Args:
            coro: Coroutine to execute
            timeout: Optional timeout override
            key: Optional key for custom timeout

        Returns:
            Coroutine result

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if timeout is None:
            config = self.get_timeout(key)
            timeout = config.total

        return await asyncio.wait_for(coro, timeout=timeout)

    async def execute_with_timeout_config[T](
        self,
        coro: Any,
        config: TimeoutConfig,
    ) -> T:
        """
        Execute with specific timeout config.

        Args:
            coro: Coroutine to execute
            config: Timeout configuration

        Returns:
            Coroutine result
        """
        return await asyncio.wait_for(coro, timeout=config.total)

    def get_stats(self) -> dict[str, Any]:
        """Get timeout controller statistics."""
        return {
            "default_config": {
                "connect": self._default_config.connect,
                "read": self._default_config.read,
                "total": self._default_config.total,
            },
            "custom_timeouts": len(self._custom_timeouts),
        }


class TimeoutContext:
    """Context manager for timeout operations."""

    def __init__(
        self,
        timeout: float,
        on_timeout: Any | None = None,
    ) -> None:
        """
        Initialize timeout context.

        Args:
            timeout: Timeout in seconds
            on_timeout: Optional callback on timeout
        """
        self._timeout = timeout
        self._on_timeout = on_timeout
        self._task: asyncio.Task | None = None
        self._timed_out = False

    @property
    def timed_out(self) -> bool:
        """Check if operation timed out."""
        return self._timed_out

    async def __aenter__(self) -> "TimeoutContext":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        return False

    async def run[T](self, coro: Any) -> T:
        """
        Run coroutine with timeout.

        Args:
            coro: Coroutine to run

        Returns:
            Coroutine result

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        try:
            return await asyncio.wait_for(coro, timeout=self._timeout)
        except TimeoutError:
            self._timed_out = True
            if self._on_timeout:
                await self._on_timeout()
            raise
