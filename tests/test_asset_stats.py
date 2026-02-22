"""Tests for asset and stats centers."""


from scheduler.asset_center import AUTO_TAG_RULES, AssetCenter
from scheduler.stats_center import StatsCollector, StatsReporter


class TestAssetCenter:
    """Tests for AssetCenter."""

    def test_auto_tag_with_port_22(self) -> None:
        """Test auto-tagging with SSH port."""
        center = AssetCenter()
        tags = center._auto_tag(
            ip="192.168.1.1",
            domain=None,
            port=22,
            service=None,
            fingerprints=None,
        )
        assert "ssh" in tags

    def test_auto_tag_with_port_3306(self) -> None:
        """Test auto-tagging with MySQL port."""
        center = AssetCenter()
        tags = center._auto_tag(
            ip="192.168.1.1",
            domain=None,
            port=3306,
            service=None,
            fingerprints=None,
        )
        assert "mysql" in tags

    def test_auto_tag_with_admin_path(self) -> None:
        """Test auto-tagging with admin path."""
        center = AssetCenter()
        tags = center._auto_tag(
            ip="192.168.1.1",
            domain="admin.example.com",
            port=80,
            service={"name": "http", "banner": "Location: /admin/login"},
            fingerprints=None,
        )
        assert "admin" in tags

    def test_auto_tag_with_fingerprints(self) -> None:
        """Test auto-tagging with fingerprint tags."""
        center = AssetCenter()
        tags = center._auto_tag(
            ip="192.168.1.1",
            domain=None,
            port=443,
            service={"name": "https"},
            fingerprints=[{"type": "webserver", "name": "nginx", "tags": ["proxy", "web"]}],
        )
        assert "proxy" in tags
        assert "web" in tags

    def test_add_custom_tag_rule(self) -> None:
        """Test adding custom tag rules."""
        center = AssetCenter()
        center.add_tag_rule(r":9000$", "php-fpm")

        tags = center._auto_tag(
            ip="192.168.1.1",
            domain=None,
            port=9000,
            service=None,
            fingerprints=None,
        )
        assert "php-fpm" in tags

    def test_tag_rules_count(self) -> None:
        """Test that default tag rules are loaded."""
        assert len(AUTO_TAG_RULES) > 0


class TestStatsCollector:
    """Tests for StatsCollector."""

    def test_collector_creation(self) -> None:
        """Test creating a stats collector."""
        collector = StatsCollector()
        assert collector is not None
        assert collector._pending_records == []

    def test_cache_initialization(self) -> None:
        """Test cache initialization."""
        collector = StatsCollector()
        assert collector._cache == {}


class TestStatsReporter:
    """Tests for StatsReporter."""

    def test_reporter_creation(self) -> None:
        """Test creating a stats reporter."""
        reporter = StatsReporter()
        assert reporter is not None
