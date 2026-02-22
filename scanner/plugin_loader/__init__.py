"""Plugin Loader - Hot loading and sandbox isolation."""

import hashlib
import importlib.util
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class PluginInfo:
    """Plugin metadata container."""

    def __init__(
        self,
        plugin_id: str,
        name: str,
        plugin_type: str,
        file_path: str,
        md5: str,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.name = name
        self.plugin_type = plugin_type
        self.file_path = file_path
        self.md5 = md5
        self.enabled = enabled
        self.metadata = metadata or {}
        self._instance: Any = None

    @property
    def instance(self) -> Any:
        """Get plugin instance."""
        return self._instance

    @instance.setter
    def instance(self, value: Any) -> None:
        self._instance = value


class Sandbox:
    """Sandbox for safe plugin execution."""

    # Allowed modules
    ALLOWED_MODULES = {
        "httpx",
        "requests",
        "json",
        "re",
        "asyncio",
        "datetime",
        "hashlib",
        "base64",
        "urllib.parse",
        "socket",
        "ssl",
        "struct",
        "binascii",
    }

    # Blocked builtins
    BLOCKED_BUILTINS = {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
    }

    def __init__(self) -> None:
        self._restricted_globals: dict[str, Any] = {}

    def create_restricted_globals(self) -> dict[str, Any]:
        """Create restricted global namespace."""
        import builtins

        safe_builtins = {}
        for name in dir(builtins):
            if name not in self.BLOCKED_BUILTINS and not name.startswith("_"):
                safe_builtins[name] = getattr(builtins, name)

        return {"__builtins__": safe_builtins}

    def check_import(self, module_name: str) -> bool:
        """Check if module import is allowed."""
        # Check full module name first (e.g., urllib.parse)
        if module_name in self.ALLOWED_MODULES:
            return True
        # Then check base module (e.g., httpx from httpx.Client)
        base_module = module_name.split(".")[0]
        return base_module in self.ALLOWED_MODULES


class PluginLoader:
    """Plugin loader with hot reload support."""

    def __init__(
        self,
        vuln_plugin_dir: str = "plugins/vulns",
        tool_plugin_dir: str = "plugins/tools",
    ) -> None:
        self._vuln_dir = Path(vuln_plugin_dir)
        self._tool_dir = Path(tool_plugin_dir)
        self._plugins: dict[str, PluginInfo] = {}
        self._tools: dict[str, Any] = {}
        self._sandbox = Sandbox()
        self._observer: Observer | None = None
        self._on_reload_callback: Callable[[str], None] | None = None

    def set_reload_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for plugin reload events."""
        self._on_reload_callback = callback

    def load_all(self) -> int:
        """Load all plugins from directories."""
        count = 0

        # Load vulnerability plugins
        if self._vuln_dir.exists():
            for py_file in self._vuln_dir.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue
                try:
                    if self._load_vuln_plugin(py_file):
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to load vuln plugin {py_file}: {e}")

        # Load tool plugins
        if self._tool_dir.exists():
            for py_file in self._tool_dir.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue
                try:
                    if self._load_tool_plugin(py_file):
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to load tool plugin {py_file}: {e}")

        logger.info(f"Loaded {count} plugins")
        return count

    def _load_vuln_plugin(self, path: Path) -> bool:
        """Load a vulnerability plugin."""
        md5 = self._calculate_md5(path)
        plugin_id = path.stem

        # Check if already loaded with same MD5
        if plugin_id in self._plugins and self._plugins[plugin_id].md5 == md5:
            return False

        # Load module
        spec = importlib.util.spec_from_file_location(plugin_id, path)
        if not spec or not spec.loader:
            return False

        module = importlib.util.module_from_spec(spec)

        # Check for vuln info
        spec.loader.exec_module(module)

        if not hasattr(module, "__vuln_info__"):
            logger.warning(f"Plugin {path} missing __vuln_info__")
            return False

        vuln_info = module.__vuln_info__
        plugin_info = PluginInfo(
            plugin_id=plugin_id,
            name=vuln_info.get("name", plugin_id),
            plugin_type="vuln",
            file_path=str(path),
            md5=md5,
            metadata=vuln_info,
        )

        # Find VulnCheck class
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and hasattr(attr, "verify"):
                plugin_info.instance = attr
                break

        self._plugins[plugin_id] = plugin_info
        logger.debug(f"Loaded vuln plugin: {plugin_id}")
        return True

    def _load_tool_plugin(self, path: Path) -> bool:
        """Load a tool plugin."""
        md5 = self._calculate_md5(path)
        tool_id = path.stem

        # Check if already loaded with same MD5
        if tool_id in self._tools and hasattr(self._tools[tool_id], "_md5"):
            if self._tools[tool_id]._md5 == md5:
                return False

        # Load module
        spec = importlib.util.spec_from_file_location(tool_id, path)
        if not spec or not spec.loader:
            return False

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find tool class
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and not attr_name.startswith("_"):
                # Instantiate and store
                instance = attr()
                instance._md5 = md5
                self._tools[tool_id] = instance
                logger.debug(f"Loaded tool plugin: {tool_id}")
                return True

        return False

    def _calculate_md5(self, path: Path) -> str:
        """Calculate MD5 hash of file."""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def get_plugin(self, plugin_id: str) -> PluginInfo | None:
        """Get plugin by ID."""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> list[PluginInfo]:
        """Get all loaded plugins."""
        return list(self._plugins.values())

    def get_tool(self, tool_id: str) -> Any | None:
        """Get tool by ID."""
        return self._tools.get(tool_id)

    def get_all_tools(self) -> dict[str, Any]:
        """Get all loaded tools."""
        return dict(self._tools)

    def reload_plugin(self, plugin_id: str) -> bool:
        """Reload a specific plugin."""
        if plugin_id not in self._plugins:
            return False

        plugin_info = self._plugins[plugin_id]
        path = Path(plugin_info.file_path)

        if not path.exists():
            del self._plugins[plugin_id]
            return False

        if self._load_vuln_plugin(path):
            if self._on_reload_callback:
                self._on_reload_callback(plugin_id)
            return True

        return False

    def start_watcher(self) -> None:
        """Start file system watcher for hot reload."""
        if self._observer:
            return

        handler = _PluginEventHandler(self)

        self._observer = Observer()
        if self._vuln_dir.exists():
            self._observer.schedule(handler, str(self._vuln_dir), recursive=True)
        if self._tool_dir.exists():
            self._observer.schedule(handler, str(self._tool_dir), recursive=True)

        self._observer.start()
        logger.info("Plugin watcher started")

    def stop_watcher(self) -> None:
        """Stop file system watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Plugin watcher stopped")


class _PluginEventHandler(FileSystemEventHandler):
    """Event handler for plugin file changes."""

    def __init__(self, loader: PluginLoader) -> None:
        self.loader = loader

    def on_modified(self, event: Any) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix == ".py" and not path.name.startswith("_"):
            logger.debug(f"Plugin modified: {path}")
            self.loader.reload_plugin(path.stem)

    def on_created(self, event: Any) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix == ".py" and not path.name.startswith("_"):
            logger.debug(f"Plugin created: {path}")
            if "vulns" in str(path):
                self.loader._load_vuln_plugin(path)
            elif "tools" in str(path):
                self.loader._load_tool_plugin(path)


# Global plugin loader instance
plugin_loader = PluginLoader()
