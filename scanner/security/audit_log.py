"""Audit Logger - Security audit logging."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"

    # Task events
    TASK_CREATE = "task_create"
    TASK_START = "task_start"
    TASK_STOP = "task_stop"
    TASK_DELETE = "task_delete"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"

    # Scan events
    SCAN_START = "scan_start"
    SCAN_STOP = "scan_stop"
    VULN_FOUND = "vuln_found"

    # Plugin events
    PLUGIN_LOAD = "plugin_load"
    PLUGIN_RELOAD = "plugin_reload"
    PLUGIN_ERROR = "plugin_error"

    # Configuration events
    CONFIG_CHANGE = "config_change"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ERROR = "error"

    # Data access events
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data."""

    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    message: str = ""
    user_id: str | None = None
    source_ip: str | None = None
    target: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "user_id": self.user_id,
            "source_ip": self.source_ip,
            "target": self.target,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger for security events.

    Features:
    - Multiple output handlers (file, console, database)
    - Log rotation
    - Event filtering
    - Async logging
    """

    def __init__(
        self,
        log_dir: str = "logs/audit",
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB
        max_files: int = 10,
        enable_console: bool = True,
        enable_file: bool = True,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            log_dir: Directory for log files
            max_file_size: Maximum file size before rotation
            max_files: Maximum number of log files to keep
            enable_console: Enable console output
            enable_file: Enable file output
        """
        self._log_dir = Path(log_dir)
        self._max_file_size = max_file_size
        self._max_files = max_files
        self._enable_console = enable_console
        self._enable_file = enable_file
        self._current_file: Path | None = None
        self._file_handle: Any = None
        self._lock = asyncio.Lock()
        self._filters: list[Callable[[AuditEvent], bool]] = []
        self._handlers: list[Callable[[AuditEvent], None]] = []

        # Statistics
        self._event_count = 0
        self._events_by_type: dict[str, int] = {}

    async def initialize(self) -> None:
        """Initialize the audit logger."""
        if self._enable_file:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            await self._rotate_if_needed()

    async def log(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: str | None = None,
        source_ip: str | None = None,
        target: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            message: Event message
            severity: Event severity
            user_id: User ID associated with event
            source_ip: Source IP address
            target: Target of the operation
            details: Additional details
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            user_id=user_id,
            source_ip=source_ip,
            target=target,
            details=details or {},
        )

        # Apply filters
        for filter_func in self._filters:
            if not filter_func(event):
                return

        # Update statistics
        self._event_count += 1
        event_key = event_type.value
        self._events_by_type[event_key] = self._events_by_type.get(event_key, 0) + 1

        # Write to handlers
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")

        # Write outputs
        await self._write_event(event)

    async def _write_event(self, event: AuditEvent) -> None:
        """Write event to configured outputs."""
        log_line = event.to_json()

        if self._enable_console:
            self._write_console(event)

        if self._enable_file:
            await self._write_file(log_line)

    def _write_console(self, event: AuditEvent) -> None:
        """Write event to console."""
        severity_map = {
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }
        level = severity_map.get(event.severity, logging.INFO)
        logger.log(level, f"[AUDIT] {event.event_type.value}: {event.message}")

    async def _write_file(self, line: str) -> None:
        """Write event to file."""
        async with self._lock:
            await self._rotate_if_needed()

            if self._file_handle:
                try:
                    self._file_handle.write(line + "\n")
                    self._file_handle.flush()
                except Exception as e:
                    logger.error(f"Failed to write audit log: {e}")

    async def _rotate_if_needed(self) -> None:
        """Rotate log file if needed."""
        if not self._enable_file:
            return

        # Get current log file
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self._log_dir / f"audit-{today}.log"

        # Check if we need to rotate
        should_rotate = False
        if self._current_file != log_file:
            should_rotate = True
        elif log_file.exists() and log_file.stat().st_size >= self._max_file_size:
            should_rotate = True

        if should_rotate:
            # Close current file
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

            # Open new file
            self._current_file = log_file
            self._file_handle = open(log_file, "a", encoding="utf-8")

            # Clean up old files
            await self._cleanup_old_files()

    async def _cleanup_old_files(self) -> None:
        """Remove old log files beyond max_files limit."""
        if not self._enable_file:
            return

        log_files = sorted(
            self._log_dir.glob("audit-*.log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for old_file in log_files[self._max_files :]:
            try:
                old_file.unlink()
            except Exception as e:
                logger.error(f"Failed to delete old audit log: {e}")

    def add_filter(self, filter_func: Callable[[AuditEvent], bool]) -> None:
        """Add an event filter."""
        self._filters.append(filter_func)

    def add_handler(self, handler: Callable[[AuditEvent], None]) -> None:
        """Add an event handler."""
        self._handlers.append(handler)

    async def close(self) -> None:
        """Close the audit logger."""
        async with self._lock:
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

    def get_stats(self) -> dict[str, Any]:
        """Get audit logger statistics."""
        return {
            "total_events": self._event_count,
            "events_by_type": dict(self._events_by_type),
            "log_dir": str(self._log_dir),
            "current_file": str(self._current_file) if self._current_file else None,
        }


# Global audit logger instance
audit_logger = AuditLogger()
