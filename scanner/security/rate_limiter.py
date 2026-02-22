"""Rate Limiter - Token bucket algorithm implementation."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from common.constants import (
    DEFAULT_RATE_LIMIT_CAPACITY,
    DEFAULT_RATE_LIMIT_RATE,
)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float = DEFAULT_RATE_LIMIT_CAPACITY
    rate: float = DEFAULT_RATE_LIMIT_RATE  # tokens per second
    _tokens: float = field(default=0.0, init=False)
    _last_update: float = field(default_factory=time.monotonic, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        """Initialize tokens to capacity."""
        self._tokens = self.capacity

    async def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True

            return False

    async def wait_for_tokens(self, tokens: float = 1.0) -> None:
        """
        Wait until tokens are available.

        Args:
            tokens: Number of tokens needed
        """
        while True:
            if await self.consume(tokens):
                return

            # Calculate wait time
            async with self._lock:
                self._refill()
                needed = tokens - self._tokens
                if needed <= 0:
                    continue
                wait_time = needed / self.rate

            await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on rate
        self._tokens = min(
            self.capacity,
            self._tokens + (elapsed * self.rate),
        )

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (without lock)."""
        return self._tokens


class RateLimiter:
    """Rate limiter with support for multiple keys."""

    def __init__(
        self,
        capacity: float = DEFAULT_RATE_LIMIT_CAPACITY,
        rate: float = DEFAULT_RATE_LIMIT_RATE,
        key_func: Callable[[str], str] | None = None,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            capacity: Maximum tokens per bucket
            rate: Token refill rate per second
            key_func: Function to extract key from identifier
        """
        self._capacity = capacity
        self._rate = rate
        self._key_func = key_func or (lambda x: x)
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, tokens: float = 1.0) -> bool:
        """
        Check if request is allowed.

        Args:
            key: Identifier for rate limiting (e.g., IP address)
            tokens: Number of tokens to consume

        Returns:
            True if allowed, False if rate limited
        """
        bucket_key = self._key_func(key)

        async with self._lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = TokenBucket(
                    capacity=self._capacity,
                    rate=self._rate,
                )
            bucket = self._buckets[bucket_key]

        return await bucket.consume(tokens)

    async def wait(self, key: str, tokens: float = 1.0) -> None:
        """
        Wait until request is allowed.

        Args:
            key: Identifier for rate limiting
            tokens: Number of tokens needed
        """
        bucket_key = self._key_func(key)

        async with self._lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = TokenBucket(
                    capacity=self._capacity,
                    rate=self._rate,
                )
            bucket = self._buckets[bucket_key]

        await bucket.wait_for_tokens(tokens)

    async def reset(self, key: str) -> None:
        """Reset bucket for a key."""
        bucket_key = self._key_func(key)

        async with self._lock:
            if bucket_key in self._buckets:
                del self._buckets[bucket_key]

    async def reset_all(self) -> None:
        """Reset all buckets."""
        async with self._lock:
            self._buckets.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "total_buckets": len(self._buckets),
            "capacity": self._capacity,
            "rate": self._rate,
            "buckets": {
                key: {
                    "available_tokens": bucket.available_tokens,
                    "capacity": bucket.capacity,
                }
                for key, bucket in self._buckets.items()
            },
        }
