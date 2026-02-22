"""Stats Center - Statistics collection and reporting."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.stat import StatRecord
from common.utils.database import get_db_context

logger = logging.getLogger(__name__)


class StatsCollector:
    """Collects and aggregates statistics."""

    def __init__(self) -> None:
        self._pending_records: list[StatRecord] = []
        self._cache: dict[str, Any] = {}

    async def record(
        self,
        vuln_id: str,
        target_id: str,
        task_id: str,
        status: str,
        duration: int | None = None,
        result: dict[str, Any] | None = None,
    ) -> StatRecord:
        """Record a stat entry."""
        import json

        async with get_db_context() as db:
            record = StatRecord(
                vuln_id=vuln_id,
                target_id=target_id,
                task_id=task_id,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() if duration else None,
                duration=duration,
                status=status,
                result=json.dumps(result) if result else None,
            )
            db.add(record)
            await db.flush()
            await db.refresh(record)

            logger.debug(f"Recorded stat: {vuln_id} on {target_id} - {status}")
            return record

    async def batch_record(self, records: list[dict[str, Any]]) -> int:
        """Record multiple stat entries."""
        count = 0
        for rec in records:
            await self.record(
                vuln_id=rec.get("vuln_id", ""),
                target_id=rec.get("target_id", ""),
                task_id=rec.get("task_id", ""),
                status=rec.get("status", "success"),
                duration=rec.get("duration"),
                result=rec.get("result"),
            )
            count += 1
        return count


class StatsReporter:
    """Generates statistics reports."""

    def __init__(self) -> None:
        pass

    async def get_overview(self) -> dict[str, Any]:
        """Get statistics overview."""
        async with get_db_context() as db:
            # Total records
            total_result = await db.execute(select(func.count()).select_from(StatRecord))
            total_records = total_result.scalar() or 0

            # By status
            status_result = await db.execute(
                select(StatRecord.status, func.count().label("count"))
                .group_by(StatRecord.status)
            )
            by_status = {row.status: row.count for row in status_result}

            # Success rate
            success_count = by_status.get("success", 0)
            success_rate = (success_count / total_records * 100) if total_records > 0 else 0

            # Average duration
            duration_result = await db.execute(
                select(func.avg(StatRecord.duration)).where(StatRecord.duration.isnot(None))
            )
            avg_duration = duration_result.scalar() or 0

            return {
                "total_records": total_records,
                "by_status": by_status,
                "success_rate": round(success_rate, 2),
                "avg_duration_ms": int(avg_duration),
            }

    async def get_vuln_stats(
        self,
        vuln_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get statistics by vulnerability ID."""
        async with get_db_context() as db:
            query = select(StatRecord)

            if vuln_id:
                query = query.where(StatRecord.vuln_id == vuln_id)
            if start_date:
                query = query.where(StatRecord.start_time >= start_date)
            if end_date:
                query = query.where(StatRecord.start_time <= end_date)

            result = await db.execute(query)
            records = result.scalars().all()

            # Aggregate by vuln_id
            stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {
                    "vuln_id": "",
                    "total": 0,
                    "success": 0,
                    "fail": 0,
                    "timeout": 0,
                    "total_duration": 0,
                    "vulnerable_count": 0,
                }
            )

            for rec in records:
                key = rec.vuln_id
                stats[key]["vuln_id"] = rec.vuln_id
                stats[key]["total"] += 1
                stats[key][rec.status] = stats[key].get(rec.status, 0) + 1
                if rec.duration:
                    stats[key]["total_duration"] += rec.duration

            # Calculate rates
            result_list = []
            for vuln_id, data in stats.items():
                total = data["total"]
                success = data["success"]
                vulnerable = data["vulnerable_count"]

                result_list.append({
                    "vuln_id": vuln_id,
                    "total_executions": total,
                    "success_count": success,
                    "fail_count": data.get("fail", 0),
                    "timeout_count": data.get("timeout", 0),
                    "success_rate": round((success / total * 100), 2) if total > 0 else 0,
                    "avg_duration_ms": int(data["total_duration"] / total) if total > 0 else 0,
                })

            return result_list

    async def get_task_stats(self, task_id: str) -> dict[str, Any]:
        """Get statistics for a specific task."""
        async with get_db_context() as db:
            # Total records
            total_result = await db.execute(
                select(func.count()).select_from(StatRecord).where(StatRecord.task_id == task_id)
            )
            total = total_result.scalar() or 0

            # By status
            status_result = await db.execute(
                select(StatRecord.status, func.count().label("count"))
                .where(StatRecord.task_id == task_id)
                .group_by(StatRecord.status)
            )
            by_status = {row.status: row.count for row in status_result}

            # Vulnerable count (from result JSON)
            vuln_result = await db.execute(
                select(StatRecord).where(
                    StatRecord.task_id == task_id,
                    StatRecord.result.contains("vulnerable"),
                )
            )
            vuln_records = vuln_result.scalars().all()

            return {
                "task_id": task_id,
                "total_checks": total,
                "by_status": by_status,
                "vulnerable_count": len(vuln_records),
            }

    async def get_daily_stats(
        self,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get daily statistics for the past N days."""
        async with get_db_context() as db:
            start_date = datetime.utcnow() - timedelta(days=days)

            result = await db.execute(
                select(StatRecord).where(StatRecord.start_time >= start_date)
            )
            records = result.scalars().all()

            # Aggregate by date
            daily_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"date": "", "total": 0, "success": 0, "fail": 0, "timeout": 0}
            )

            for rec in records:
                date_key = rec.start_time.strftime("%Y-%m-%d")
                daily_stats[date_key]["date"] = date_key
                daily_stats[date_key]["total"] += 1
                daily_stats[date_key][rec.status] = daily_stats[date_key].get(rec.status, 0) + 1

            return sorted(daily_stats.values(), key=lambda x: x["date"])


# Global instances
stats_collector = StatsCollector()
stats_reporter = StatsReporter()
