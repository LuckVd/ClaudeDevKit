"""HTTP Client Tool - A reusable HTTP client for vulnerability plugins."""

import asyncio
from typing import Any

import httpx


class HttpClient:
    """HTTP client with connection pooling and retry support."""

    def __init__(self, timeout: float = 10.0, max_retries: int = 3) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                verify=False,
            )
        return self._client

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send GET request."""
        client = await self._get_client()
        for attempt in range(self._max_retries):
            try:
                return await client.get(url, headers=headers, params=params)
            except httpx.TransportError:
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError("Unreachable")

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Send POST request."""
        client = await self._get_client()
        for attempt in range(self._max_retries):
            try:
                return await client.post(
                    url, headers=headers, data=data, json=json
                )
            except httpx.TransportError:
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError("Unreachable")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
