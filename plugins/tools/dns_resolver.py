"""DNS Resolver Tool - DNS lookup utilities for vulnerability plugins."""

import asyncio
import socket
from typing import Any

import dns.asyncresolver
import dns.resolver


class DnsResolver:
    """DNS resolver with caching support."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout
        self._cache: dict[str, Any] = {}

    async def resolve_a(self, domain: str) -> list[str]:
        """Resolve A records."""
        cache_key = f"A:{domain}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            resolver = dns.asyncresolver.Resolver()
            resolver.timeout = self._timeout
            resolver.lifetime = self._timeout

            answer = await resolver.resolve(domain, "A")
            result = [str(rdata) for rdata in answer]
            self._cache[cache_key] = result
            return result
        except dns.resolver.NXDOMAIN:
            return []
        except dns.resolver.NoAnswer:
            return []

    async def resolve_cname(self, domain: str) -> str | None:
        """Resolve CNAME record."""
        cache_key = f"CNAME:{domain}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            resolver = dns.asyncresolver.Resolver()
            resolver.timeout = self._timeout
            resolver.lifetime = self._timeout

            answer = await resolver.resolve(domain, "CNAME")
            result = str(answer[0].target).rstrip(".")
            self._cache[cache_key] = result
            return result
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return None

    async def reverse_dns(self, ip: str) -> str | None:
        """Reverse DNS lookup."""
        cache_key = f"PTR:{ip}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, socket.gethostbyaddr, ip
            )
            hostname = result[0]
            self._cache[cache_key] = hostname
            return hostname
        except socket.herror:
            return None

    def clear_cache(self) -> None:
        """Clear DNS cache."""
        self._cache.clear()
