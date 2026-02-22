"""Asset Center - Asset discovery, storage, and tagging."""

import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.target import Fingerprint, Service, Target
from common.utils.database import get_db_context

logger = logging.getLogger(__name__)


# Auto-tagging rules
AUTO_TAG_RULES = [
    {"pattern": r"/admin", "tag": "admin"},
    {"pattern": r"/manager", "tag": "manager"},
    {"pattern": r"/api", "tag": "api"},
    {"pattern": r"/console", "tag": "console"},
    {"pattern": r":22$", "tag": "ssh"},
    {"pattern": r":3306$", "tag": "mysql"},
    {"pattern": r":5432$", "tag": "postgresql"},
    {"pattern": r":6379$", "tag": "redis"},
    {"pattern": r":27017$", "tag": "mongodb"},
    {"pattern": r":8080$", "tag": "web-alt"},
]


class AssetCenter:
    """Centralized asset management."""

    def __init__(self) -> None:
        self._tag_rules = list(AUTO_TAG_RULES)
        self._custom_rules: list[dict[str, Any]] = []

    def add_tag_rule(self, pattern: str, tag: str) -> None:
        """Add a custom tagging rule."""
        self._custom_rules.append({"pattern": pattern, "tag": tag})

    def load_tag_rules(self, rules: list[dict[str, str]]) -> None:
        """Load tagging rules from list."""
        for rule in rules:
            self.add_tag_rule(rule.get("pattern", ""), rule.get("tag", ""))

    async def discover_asset(
        self,
        ip: str | None = None,
        domain: str | None = None,
        port: int | None = None,
        service: dict[str, Any] | None = None,
        fingerprints: list[dict[str, Any]] | None = None,
        discovered_by: str | None = None,
    ) -> Target:
        """Discover and store a new asset."""
        async with get_db_context() as db:
            # Check for existing asset
            existing = await self._find_existing(db, ip, domain)
            if existing:
                # Update existing asset
                await self._update_asset(
                    db, existing, port, service, fingerprints
                )
                await db.flush()
                await db.refresh(existing)
                return existing

            # Create new asset
            asset = Target(
                ip=ip,
                domain=domain,
                discovered_by=discovered_by,
                last_scan=datetime.utcnow(),
            )

            # Add ports
            if port:
                asset.port_list = [port]

            # Auto-tag
            tags = self._auto_tag(ip, domain, port, service, fingerprints)
            if tags:
                asset.tag_list = tags

            db.add(asset)
            await db.flush()

            # Add service
            if service and port:
                svc = Service(
                    target_id=asset.id,
                    port=port,
                    name=service.get("name", "unknown"),
                    banner=service.get("banner"),
                    ssl=service.get("ssl", False),
                )
                db.add(svc)

            # Add fingerprints
            if fingerprints:
                for fp in fingerprints:
                    fp_record = Fingerprint(
                        target_id=asset.id,
                        type=fp.get("type", "unknown"),
                        name=fp.get("name", "unknown"),
                        version=fp.get("version"),
                        tags=",".join(fp.get("tags", [])),
                    )
                    db.add(fp_record)

            await db.flush()
            await db.refresh(asset)

            logger.info(f"Discovered new asset: {ip or domain}")
            return asset

    async def _find_existing(
        self, db: AsyncSession, ip: str | None, domain: str | None
    ) -> Target | None:
        """Find existing asset by IP or domain."""
        if ip:
            result = await db.execute(select(Target).where(Target.ip == ip))
            asset = result.scalar_one_or_none()
            if asset:
                return asset

        if domain:
            result = await db.execute(select(Target).where(Target.domain == domain))
            asset = result.scalar_one_or_none()
            if asset:
                return asset

        return None

    async def _update_asset(
        self,
        db: AsyncSession,
        asset: Target,
        port: int | None,
        service: dict[str, Any] | None,
        fingerprints: list[dict[str, Any]] | None,
    ) -> None:
        """Update existing asset with new info."""
        # Add port if not exists
        if port:
            ports = set(asset.port_list)
            ports.add(port)
            asset.port_list = list(ports)

        # Update last scan
        asset.last_scan = datetime.utcnow()

        # Add new tags
        new_tags = self._auto_tag(asset.ip, asset.domain, port, service, fingerprints)
        existing_tags = set(asset.tag_list)
        existing_tags.update(new_tags)
        asset.tag_list = list(existing_tags)

    def _auto_tag(
        self,
        ip: str | None,
        domain: str | None,
        port: int | None,
        service: dict[str, Any] | None,
        fingerprints: list[dict[str, Any]] | None,
    ) -> list[str]:
        """Generate tags based on asset info."""
        tags = set()

        # Build search string
        search_parts = []
        if domain:
            search_parts.append(domain)
        if port:
            search_parts.append(f":{port}")
        if service:
            search_parts.append(service.get("name", ""))
            search_parts.append(service.get("banner", ""))

        search_str = " ".join(search_parts).lower()

        # Apply rules
        all_rules = self._tag_rules + self._custom_rules
        for rule in all_rules:
            pattern = rule.get("pattern", "")
            tag = rule.get("tag", "")
            if pattern and tag and re.search(pattern, search_str, re.IGNORECASE):
                tags.add(tag)

        # Tag from fingerprints
        if fingerprints:
            for fp in fingerprints:
                fp_tags = fp.get("tags", [])
                tags.update(fp_tags)
                if fp.get("type") == "webserver":
                    tags.add("web")
                if fp.get("type") == "framework":
                    tags.add("web")

        return list(tags)

    async def add_tags(self, asset_id: str, tags: list[str]) -> Target | None:
        """Add tags to an asset."""
        async with get_db_context() as db:
            result = await db.execute(select(Target).where(Target.id == asset_id))
            asset = result.scalar_one_or_none()
            if not asset:
                return None

            existing = set(asset.tag_list)
            existing.update(tags)
            asset.tag_list = list(existing)

            await db.flush()
            await db.refresh(asset)
            return asset

    async def remove_tags(self, asset_id: str, tags: list[str]) -> Target | None:
        """Remove tags from an asset."""
        async with get_db_context() as db:
            result = await db.execute(select(Target).where(Target.id == asset_id))
            asset = result.scalar_one_or_none()
            if not asset:
                return None

            existing = set(asset.tag_list)
            existing.difference_update(tags)
            asset.tag_list = list(existing)

            await db.flush()
            await db.refresh(asset)
            return asset

    async def list_assets(
        self,
        tags: list[str] | None = None,
        ip_prefix: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Target], int]:
        """List assets with filtering."""
        async with get_db_context() as db:
            query = select(Target)
            count_query = select(Target.id)

            # Apply filters
            if tags:
                for tag in tags:
                    query = query.where(Target.tags.contains(tag))
                    count_query = count_query.where(Target.tags.contains(tag))

            if ip_prefix:
                query = query.where(Target.ip.startswith(ip_prefix))
                count_query = count_query.where(Target.ip.startswith(ip_prefix))

            # Count
            from sqlalchemy import func

            total_result = await db.execute(select(func.count()).select_from(Target))
            total = total_result.scalar() or 0

            # Paginate
            query = query.order_by(Target.created_at.desc())
            query = query.offset((page - 1) * size).limit(size)

            result = await db.execute(query)
            assets = result.scalars().all()

            return list(assets), total


# Global asset center instance
asset_center = AssetCenter()
