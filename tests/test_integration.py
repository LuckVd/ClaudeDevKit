"""Integration tests for VulnScan Engine."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.task import Task, TaskStatus
from common.models.target import Target
from scheduler.main import app
from scanner.node_manager import NodeManager
from scanner.coroutine_pool import CoroutinePool
from scanner.security import RateLimiter, CircuitBreaker, CircuitState
from common.observability import HealthChecker, HealthStatus


class TestTaskIntegration:
    """Integration tests for task lifecycle."""

    @pytest.mark.asyncio
    async def test_task_create_to_complete_flow(self, client: AsyncClient) -> None:
        """Test complete task lifecycle."""
        # Create task
        response = await client.post(
            "/api/v1/tasks",
            json={
                "name": "Integration Test Task",
                "targets": ["192.168.1.1", "192.168.1.2"],
                "policy": "quick",
                "priority": 5,
            },
        )
        assert response.status_code == 201
        task_data = response.json()
        assert task_data["name"] == "Integration Test Task"
        assert task_data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_task_list_pagination(self, client: AsyncClient) -> None:
        """Test task list with pagination."""
        # Create multiple tasks
        for i in range(5):
            await client.post(
                "/api/v1/tasks",
                json={
                    "name": f"Task {i}",
                    "targets": ["10.0.0.1"],
                    "policy": "quick",
                },
            )

        # List with pagination
        response = await client.get("/api/v1/tasks?skip=0&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestScannerIntegration:
    """Integration tests for scanner components."""

    @pytest.mark.asyncio
    async def test_coroutine_pool_with_tasks(self) -> None:
        """Test coroutine pool execution."""
        pool = CoroutinePool(max_size=5)
        results = []

        async def task(n: int) -> int:
            await asyncio.sleep(0.01)
            results.append(n)
            return n * 2

        # Submit multiple tasks
        futures = []
        for i in range(10):
            future = await pool.submit(task, i)
            futures.append(future)

        # Wait for completion
        await asyncio.gather(*futures)

        assert len(results) == 10
        assert pool.active_count == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_with_circuit_breaker(self) -> None:
        """Test rate limiter combined with circuit breaker."""
        limiter = RateLimiter(capacity=5, rate=1.0)
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        # Should allow initial requests
        for _ in range(3):
            allowed = await limiter.check("test_client")
            assert allowed is True

        # Circuit should be closed
        assert breaker.is_closed is True

        # Open circuit with failures
        for _ in range(3):
            await breaker.record_failure()

        assert breaker.is_open is True


class TestSecurityIntegration:
    """Integration tests for security components."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_threshold(self) -> None:
        """Test rate limiting blocks excessive requests."""
        limiter = RateLimiter(capacity=3, rate=0.5)

        # Use all tokens
        assert await limiter.check("user1") is True
        assert await limiter.check("user1") is True
        assert await limiter.check("user1") is True

        # Should be blocked
        assert await limiter.check("user1") is False

        # Different user should work
        assert await limiter.check("user2") is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self) -> None:
        """Test circuit breaker recovery flow."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )

        # Open circuit
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.is_open is True

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Should transition to half-open
        assert await breaker.can_execute() is True
        assert breaker.is_half_open is True

        # Record successes to close
        await breaker.record_success()
        await breaker.record_success()
        assert breaker.is_closed is True


class TestObservabilityIntegration:
    """Integration tests for observability."""

    @pytest.mark.asyncio
    async def test_health_check_aggregates_results(self) -> None:
        """Test health checker aggregates all checks."""
        checker = HealthChecker()

        # Register custom checks
        def check_service() -> "HealthCheckResult":
            from common.observability.health import HealthCheckResult
            return HealthCheckResult(
                name="service",
                status=HealthStatus.HEALTHY,
                message="Service OK",
            )

        checker.register_check("service", check_service)

        # Run all checks
        report = await checker.run_checks()

        assert report.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert len(report.checks) >= 1

    @pytest.mark.asyncio
    async def test_tracing_spans_are_recorded(self) -> None:
        """Test tracing records spans correctly."""
        from common.observability.tracing import TraceManager

        manager = TraceManager(service_name="test")

        with manager.trace("operation1"):
            with manager.trace("sub_operation"):
                pass

        spans = manager.get_spans()
        assert len(spans) == 2

        # Check parent-child relationship
        sub_span = [s for s in spans if s["name"] == "sub_operation"][0]
        assert sub_span["parent_span_id"] is not None


class TestPluginIntegration:
    """Integration tests for plugin system."""

    @pytest.mark.asyncio
    async def test_plugin_loader_discovers_plugins(self) -> None:
        """Test plugin loader discovers and loads plugins."""
        from scanner.plugin_loader import PluginLoader
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            vuln_dir = Path(tmpdir) / "vulns"
            tool_dir = Path(tmpdir) / "tools"
            vuln_dir.mkdir()
            tool_dir.mkdir()

            # Create test plugin
            plugin_code = '''
__vuln_info__ = {"name": "Test", "severity": "high"}

class TestVuln:
    async def verify(self, target, http_client):
        return {"vulnerable": False}
'''
            (vuln_dir / "test.py").write_text(plugin_code)

            loader = PluginLoader(
                vuln_plugin_dir=str(vuln_dir),
                tool_plugin_dir=str(tool_dir),
            )

            count = loader.load_all()
            assert count == 1

            plugin = loader.get_plugin("test")
            assert plugin is not None
            assert plugin.name == "Test"


class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_scan_flow_mocked(self, client: AsyncClient) -> None:
        """Test full scan flow with mocked components."""
        # 1. Create task
        response = await client.post(
            "/api/v1/tasks",
            json={
                "name": "E2E Test",
                "targets": ["example.com"],
                "policy": "quick",
            },
        )
        assert response.status_code == 201

        # 2. Check health
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # 3. List plugins
        response = await client.get("/api/v1/plugins")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, client: AsyncClient) -> None:
        """Test concurrent API request handling."""

        async def make_request(n: int) -> int:
            response = await client.get("/health")
            return response.status_code

        # Make concurrent requests
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(code == 200 for code in results)
