"""Tests for Plugin Loader module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scanner.plugin_loader import (
    PluginInfo,
    PluginLoader,
    Sandbox,
    plugin_loader,
)


class TestPluginInfo:
    """Tests for PluginInfo class."""

    def test_create_plugin_info(self) -> None:
        """Test creating plugin info."""
        info = PluginInfo(
            plugin_id="test-plugin",
            name="Test Plugin",
            plugin_type="vuln",
            file_path="/path/to/plugin.py",
            md5="abc123",
        )

        assert info.plugin_id == "test-plugin"
        assert info.name == "Test Plugin"
        assert info.plugin_type == "vuln"
        assert info.enabled is True
        assert info.metadata == {}

    def test_plugin_info_instance(self) -> None:
        """Test plugin instance property."""
        info = PluginInfo(
            plugin_id="test",
            name="Test",
            plugin_type="vuln",
            file_path="/path/to/plugin.py",
            md5="abc",
        )

        assert info.instance is None

        # Set instance
        mock_instance = MagicMock()
        info.instance = mock_instance
        assert info.instance is mock_instance

    def test_plugin_info_with_metadata(self) -> None:
        """Test plugin info with custom metadata."""
        metadata = {"author": "test", "version": "1.0"}
        info = PluginInfo(
            plugin_id="test",
            name="Test",
            plugin_type="vuln",
            file_path="/path",
            md5="abc",
            metadata=metadata,
        )

        assert info.metadata == metadata
        assert info.metadata["author"] == "test"


class TestSandbox:
    """Tests for Sandbox class."""

    def test_create_sandbox(self) -> None:
        """Test creating sandbox instance."""
        sandbox = Sandbox()
        assert sandbox is not None

    def test_allowed_modules(self) -> None:
        """Test allowed module list."""
        sandbox = Sandbox()

        # Should allow these modules
        assert sandbox.check_import("httpx") is True
        assert sandbox.check_import("requests") is True
        assert sandbox.check_import("json") is True
        assert sandbox.check_import("asyncio") is True

    def test_blocked_modules(self) -> None:
        """Test blocked module detection."""
        sandbox = Sandbox()

        # Should block these modules
        assert sandbox.check_import("os") is False
        assert sandbox.check_import("subprocess") is False
        assert sandbox.check_import("sys") is False

    def test_submodule_import(self) -> None:
        """Test submodule import checking."""
        sandbox = Sandbox()

        # Should allow submodule of allowed modules (urllib.parse is allowed)
        assert sandbox.check_import("urllib.parse") is True
        # httpx.Client would check base module "httpx"
        assert sandbox.check_import("httpx") is True
        # Disallowed submodule
        assert sandbox.check_import("os.path") is False

    def test_create_restricted_globals(self) -> None:
        """Test restricted globals creation."""
        sandbox = Sandbox()
        restricted = sandbox.create_restricted_globals()

        assert "__builtins__" in restricted
        builtins = restricted["__builtins__"]

        # Safe builtins should be available
        assert "print" in builtins
        assert "len" in builtins
        assert "str" in builtins

        # Dangerous builtins should be blocked
        assert "eval" not in builtins
        assert "exec" not in builtins
        assert "open" not in builtins
        assert "__import__" not in builtins


class TestPluginLoader:
    """Tests for PluginLoader class."""

    @pytest.fixture
    def temp_plugin_dirs(self) -> tuple[Path, Path]:
        """Create temporary plugin directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vuln_dir = Path(tmpdir) / "vulns"
            tool_dir = Path(tmpdir) / "tools"
            vuln_dir.mkdir()
            tool_dir.mkdir()
            yield vuln_dir, tool_dir

    def test_create_loader(self) -> None:
        """Test creating plugin loader."""
        loader = PluginLoader()
        assert loader is not None

    def test_create_loader_with_dirs(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test creating loader with custom directories."""
        vuln_dir, tool_dir = temp_plugin_dirs
        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )
        assert loader is not None

    def test_load_empty_dirs(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test loading from empty directories."""
        vuln_dir, tool_dir = temp_plugin_dirs
        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        count = loader.load_all()
        assert count == 0

    def test_load_vuln_plugin(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test loading a vulnerability plugin."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create a test plugin
        plugin_code = '''
__vuln_info__ = {
    "name": "Test Vuln",
    "severity": "high",
}

class TestVuln:
    async def verify(self, target, http_client):
        return {"vulnerable": False}
'''
        plugin_path = vuln_dir / "test_vuln.py"
        plugin_path.write_text(plugin_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        count = loader.load_all()
        assert count == 1

        # Check plugin is loaded
        plugin = loader.get_plugin("test_vuln")
        assert plugin is not None
        assert plugin.name == "Test Vuln"
        assert plugin.plugin_type == "vuln"

    def test_load_tool_plugin(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test loading a tool plugin."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create a test tool
        tool_code = '''
class TestTool:
    def __init__(self):
        self.name = "test"

    def do_something(self):
        return "done"
'''
        tool_path = tool_dir / "test_tool.py"
        tool_path.write_text(tool_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        count = loader.load_all()
        assert count == 1

        # Check tool is loaded
        tool = loader.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test"

    def test_skip_underscore_files(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test that files starting with underscore are skipped."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create files that should be skipped
        (vuln_dir / "__init__.py").write_text("")
        (vuln_dir / "_private.py").write_text("__vuln_info__ = {}")

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        count = loader.load_all()
        assert count == 0

    def test_plugin_missing_vuln_info(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test handling plugin without __vuln_info__."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create plugin without vuln_info
        plugin_code = '''
class TestVuln:
    pass
'''
        (vuln_dir / "no_info.py").write_text(plugin_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        count = loader.load_all()
        assert count == 0

    def test_md5_change_detection(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test that MD5 changes trigger reload."""
        vuln_dir, tool_dir = temp_plugin_dirs

        plugin_code = '''
__vuln_info__ = {"name": "Test"}
class TestVuln:
    pass
'''
        plugin_path = vuln_dir / "test.py"
        plugin_path.write_text(plugin_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        # First load
        count = loader.load_all()
        assert count == 1
        first_md5 = loader.get_plugin("test").md5

        # Modify and reload
        plugin_path.write_text(plugin_code + "\n# modified\n")
        count = loader.load_all()
        assert count == 1
        second_md5 = loader.get_plugin("test").md5

        assert first_md5 != second_md5

    def test_get_all_plugins(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test getting all loaded plugins."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create multiple plugins
        for i in range(3):
            plugin_code = f'''
__vuln_info__ = {{"name": "Test {i}"}}
class TestVuln{i}:
    pass
'''
            (vuln_dir / f"test_{i}.py").write_text(plugin_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        loader.load_all()
        plugins = loader.get_all_plugins()

        assert len(plugins) == 3

    def test_get_all_tools(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test getting all loaded tools."""
        vuln_dir, tool_dir = temp_plugin_dirs

        # Create multiple tools
        for i in range(2):
            tool_code = f'''
class Tool{i}:
    def __init__(self):
        self.id = {i}
'''
            (tool_dir / f"tool_{i}.py").write_text(tool_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        loader.load_all()
        tools = loader.get_all_tools()

        assert len(tools) == 2

    def test_reload_callback(self, temp_plugin_dirs: tuple[Path, Path]) -> None:
        """Test reload callback is called."""
        vuln_dir, tool_dir = temp_plugin_dirs

        plugin_code = '''
__vuln_info__ = {"name": "Test"}
class TestVuln:
    pass
'''
        plugin_path = vuln_dir / "test.py"
        plugin_path.write_text(plugin_code)

        loader = PluginLoader(
            vuln_plugin_dir=str(vuln_dir),
            tool_plugin_dir=str(tool_dir),
        )

        callback_called = []

        def on_reload(plugin_id: str) -> None:
            callback_called.append(plugin_id)

        loader.set_reload_callback(on_reload)
        loader.load_all()

        # Modify and force reload
        plugin_path.write_text(plugin_code + "\n# modified\n")
        loader.reload_plugin("test")

        assert "test" in callback_called


class TestGlobalLoader:
    """Tests for global plugin loader instance."""

    def test_global_instance_exists(self) -> None:
        """Test that global plugin loader instance exists."""
        assert plugin_loader is not None
        assert isinstance(plugin_loader, PluginLoader)
