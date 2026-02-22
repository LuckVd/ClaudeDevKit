"""Tests for Security module."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from scanner.security import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    RateLimiter,
    TimeoutConfig,
    TimeoutController,
    TokenBucket,
)


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_create_bucket(self) -> None:
        """Test creating a token bucket."""
        bucket = TokenBucket(capacity=10, rate=2.0)
        assert bucket.capacity == 10
        assert bucket.rate == 2.0
        assert bucket.available_tokens == 10

    @pytest.mark.asyncio
    async def test_consume_tokens(self) -> None:
        """Test consuming tokens."""
        bucket = TokenBucket(capacity=10, rate=2.0)

        # Should succeed
        result = await bucket.consume(5)
        assert result is True
        assert bucket.available_tokens == 5

    @pytest.mark.asyncio
    async def test_consume_too_many_tokens(self) -> None:
        """Test consuming more tokens than available."""
        bucket = TokenBucket(capacity=10, rate=2.0)

        # Should fail - not enough tokens
        result = await bucket.consume(15)
        assert result is False

    @pytest.mark.asyncio
    async def test_token_refill(self) -> None:
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, rate=10.0)  # 10 tokens/sec

        # Consume all tokens
        await bucket.consume(10)
        assert bucket.available_tokens == 0

        # Wait a bit
        await asyncio.sleep(0.2)

        # Force refill by consuming
        bucket._refill()

        # Should have refilled some tokens
        assert bucket.available_tokens > 0

    @pytest.mark.asyncio
    async def test_wait_for_tokens(self) -> None:
        """Test waiting for tokens."""
        bucket = TokenBucket(capacity=5, rate=100.0)

        # Consume all
        await bucket.consume(5)

        # Wait should succeed after refill
        await bucket.wait_for_tokens(1)
        assert True  # If we get here, wait succeeded


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_create_rate_limiter(self) -> None:
        """Test creating a rate limiter."""
        limiter = RateLimiter(capacity=10, rate=5.0)
        assert limiter is not None

    @pytest.mark.asyncio
    async def test_check_allows_request(self) -> None:
        """Test that rate limiter allows requests."""
        limiter = RateLimiter(capacity=10, rate=5.0)

        for _ in range(5):
            result = await limiter.check("test_key")
            assert result is True

    @pytest.mark.asyncio
    async def test_check_blocks_over_limit(self) -> None:
        """Test that rate limiter blocks over limit."""
        limiter = RateLimiter(capacity=3, rate=0.1)  # Very slow refill

        # Use all tokens
        for _ in range(3):
            await limiter.check("test_key")

        # Should be blocked
        result = await limiter.check("test_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_different_keys_independent(self) -> None:
        """Test that different keys have independent buckets."""
        limiter = RateLimiter(capacity=2, rate=0.1)

        # Exhaust key1
        await limiter.check("key1")
        await limiter.check("key1")

        # key1 should be blocked
        assert await limiter.check("key1") is False

        # key2 should still work
        assert await limiter.check("key2") is True

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        """Test resetting a key."""
        limiter = RateLimiter(capacity=2, rate=0.1)

        # Exhaust
        await limiter.check("test_key")
        await limiter.check("test_key")
        assert await limiter.check("test_key") is False

        # Reset
        await limiter.reset("test_key")

        # Should work again
        assert await limiter.check("test_key") is True

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test getting statistics."""
        limiter = RateLimiter(capacity=10, rate=5.0)
        await limiter.check("key1")
        await limiter.check("key2")

        stats = limiter.get_stats()
        assert stats["total_buckets"] == 2
        assert stats["capacity"] == 10
        assert stats["rate"] == 5.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_create_circuit_breaker(self) -> None:
        """Test creating a circuit breaker."""
        cb = CircuitBreaker(name="test")
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_allows_when_closed(self) -> None:
        """Test that requests are allowed when closed."""
        cb = CircuitBreaker(name="test")

        for _ in range(10):
            assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_opens_on_failures(self) -> None:
        """Test that circuit opens after failures."""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        # Record failures
        for _ in range(3):
            await cb.record_failure()

        assert cb.is_open is True
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self) -> None:
        """Test transition to half-open after timeout."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.1,
        )

        # Open the circuit
        await cb.record_failure()
        assert cb.is_open is True

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Should transition to half-open
        assert await cb.can_execute() is True
        assert cb.is_half_open is True

    @pytest.mark.asyncio
    async def test_closes_on_success_in_half_open(self) -> None:
        """Test circuit closes on success in half-open."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=2,
        )

        # Open and wait for half-open
        await cb.record_failure()
        await asyncio.sleep(0.2)
        await cb.can_execute()

        # Record successes
        await cb.record_success()
        assert cb.is_half_open is True  # Not enough yet

        await cb.record_success()
        assert cb.is_closed is True  # Now closed

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test executing a successful function."""
        cb = CircuitBreaker(name="test")

        async def success_func() -> str:
            return "success"

        result = await cb.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_blocked_when_open(self) -> None:
        """Test execute raises error when open."""
        cb = CircuitBreaker(name="test", failure_threshold=1)

        async def fail_func() -> None:
            raise ValueError("test error")

        # Open the circuit
        try:
            await cb.execute(fail_func)
        except ValueError:
            pass

        assert cb.is_open is True

        # Should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await cb.execute(lambda: "test")

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        """Test resetting circuit breaker."""
        cb = CircuitBreaker(name="test", failure_threshold=1)

        # Open
        await cb.record_failure()
        assert cb.is_open is True

        # Reset
        await cb.reset()
        assert cb.is_closed is True

    def test_get_stats(self) -> None:
        """Test getting statistics."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        stats = cb.get_stats()

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 5


class TestTimeoutController:
    """Tests for TimeoutController class."""

    def test_create_controller(self) -> None:
        """Test creating a timeout controller."""
        controller = TimeoutController()
        assert controller is not None

    def test_create_with_config(self) -> None:
        """Test creating with custom config."""
        config = TimeoutConfig(connect=5.0, read=10.0, total=30.0)
        controller = TimeoutController(default_config=config)

        retrieved = controller.get_timeout()
        assert retrieved.connect == 5.0
        assert retrieved.read == 10.0
        assert retrieved.total == 30.0

    def test_set_custom_timeout(self) -> None:
        """Test setting custom timeout for a key."""
        controller = TimeoutController()
        custom = TimeoutConfig(connect=1.0, read=2.0, total=5.0)

        controller.set_timeout("slow_target", custom)

        retrieved = controller.get_timeout("slow_target")
        assert retrieved.total == 5.0

    def test_get_default_timeout(self) -> None:
        """Test getting default timeout for unknown key."""
        controller = TimeoutController()
        default = controller.get_timeout("unknown_key")
        assert default is not None

    @pytest.mark.asyncio
    async def test_execute_with_timeout_success(self) -> None:
        """Test executing with timeout - success case."""
        controller = TimeoutController()

        async def quick_func() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await controller.execute_with_timeout(
            quick_func(), timeout=1.0
        )
        assert result == "done"

    @pytest.mark.asyncio
    async def test_execute_with_timeout_exceeded(self) -> None:
        """Test executing with timeout - timeout case."""
        controller = TimeoutController()

        async def slow_func() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await controller.execute_with_timeout(slow_func(), timeout=0.1)

    def test_to_httpx_timeout(self) -> None:
        """Test converting to httpx format."""
        config = TimeoutConfig(connect=5.0, read=10.0, total=30.0)
        httpx_timeout = config.to_httpx_timeout()

        assert httpx_timeout["connect"] == 5.0
        assert httpx_timeout["read"] == 10.0

    def test_get_stats(self) -> None:
        """Test getting statistics."""
        controller = TimeoutController()
        stats = controller.get_stats()

        assert "default_config" in stats
        assert "custom_timeouts" in stats


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def temp_log_dir(self) -> Path:
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_create_logger(self, temp_log_dir: Path) -> None:
        """Test creating an audit logger."""
        logger = AuditLogger(
            log_dir=str(temp_log_dir),
            enable_file=False,
        )
        assert logger is not None

    @pytest.mark.asyncio
    async def test_log_event(self, temp_log_dir: Path) -> None:
        """Test logging an event."""
        audit = AuditLogger(
            log_dir=str(temp_log_dir),
            enable_file=False,
        )

        await audit.log(
            event_type=AuditEventType.TASK_CREATE,
            message="Test task created",
            user_id="user1",
        )

        stats = audit.get_stats()
        assert stats["total_events"] == 1
        assert stats["events_by_type"]["task_create"] == 1

    @pytest.mark.asyncio
    async def test_log_with_details(self, temp_log_dir: Path) -> None:
        """Test logging with details."""
        audit = AuditLogger(
            log_dir=str(temp_log_dir),
            enable_file=False,
        )

        await audit.log(
            event_type=AuditEventType.VULN_FOUND,
            message="SQL injection found",
            severity=AuditSeverity.ERROR,
            target="http://example.com",
            details={"vuln_type": "sqli", "param": "id"},
        )

        stats = audit.get_stats()
        assert stats["total_events"] == 1

    @pytest.mark.asyncio
    async def test_file_logging(self, temp_log_dir: Path) -> None:
        """Test logging to file."""
        audit = AuditLogger(
            log_dir=str(temp_log_dir),
            enable_file=True,
            enable_console=False,
        )

        await audit.initialize()
        await audit.log(
            event_type=AuditEventType.SYSTEM_START,
            message="System started",
        )
        await audit.close()

        # Check file was created
        log_files = list(temp_log_dir.glob("audit-*.log"))
        assert len(log_files) == 1

    @pytest.mark.asyncio
    async def test_event_filter(self, temp_log_dir: Path) -> None:
        """Test event filtering."""
        audit = AuditLogger(
            log_dir=str(temp_log_dir),
            enable_file=False,
        )

        # Add filter to exclude INFO severity
        audit.add_filter(lambda e: e.severity != AuditSeverity.INFO)

        await audit.log(
            event_type=AuditEventType.TASK_CREATE,
            message="Info event",
            severity=AuditSeverity.INFO,
        )

        await audit.log(
            event_type=AuditEventType.ERROR,
            message="Error event",
            severity=AuditSeverity.ERROR,
        )

        stats = audit.get_stats()
        assert stats["total_events"] == 1  # Only error logged


class TestAuditEvent:
    """Tests for AuditEvent class."""

    def test_create_event(self) -> None:
        """Test creating an audit event."""
        event = AuditEvent(
            event_type=AuditEventType.LOGIN,
            message="User logged in",
            user_id="user1",
        )

        assert event.event_type == AuditEventType.LOGIN
        assert event.message == "User logged in"
        assert event.severity == AuditSeverity.INFO

    def test_event_to_dict(self) -> None:
        """Test converting event to dict."""
        event = AuditEvent(
            event_type=AuditEventType.VULN_FOUND,
            severity=AuditSeverity.ERROR,
            message="XSS found",
            target="http://test.com",
        )

        data = event.to_dict()

        assert data["event_type"] == "vuln_found"
        assert data["severity"] == "error"
        assert data["message"] == "XSS found"
        assert data["target"] == "http://test.com"
        assert "timestamp" in data

    def test_event_to_json(self) -> None:
        """Test converting event to JSON."""
        event = AuditEvent(
            event_type=AuditEventType.TASK_START,
            message="Task started",
        )

        json_str = event.to_json()

        assert "task_start" in json_str
        assert "Task started" in json_str
