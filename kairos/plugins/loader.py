import importlib
import logging
from pathlib import Path
from typing import Any

from kairos.core.exceptions import PluginLoadError
from .base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """D4: Dynamic plugin loader with profile-based configuration."""

    def __init__(self):
        self._instances: dict[str, BasePlugin] = {}
        self._profile_plugins: dict[str, list[BasePlugin]] = {}

    def load(self, plugin_path: str, config: dict | None = None) -> BasePlugin:
        """Load a single plugin by dotted path (e.g. 'kairos.plugins.safety.SafetyFilter')."""
        if plugin_path in self._instances:
            return self._instances[plugin_path]
        try:
            mod_path, cls_name = plugin_path.rsplit(".", 1)
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            instance = cls(**(config or {}))
            self._instances[plugin_path] = instance
            logger.info("Loaded plugin: %s", plugin_path)
            return instance
        except (ImportError, AttributeError, TypeError) as e:
            raise PluginLoadError(plugin_path, str(e)) from e

    def load_for_profile(self, profile_id: str, plugin_configs: list[dict]) -> list[BasePlugin]:
        """Load all plugins configured for a profile."""
        if profile_id in self._profile_plugins:
            return self._profile_plugins[profile_id]

        plugins = []
        for cfg in plugin_configs:
            path = cfg.get("path", "")
            if not path:
                continue
            try:
                plugin = self.load(path, cfg.get("config"))
                plugins.append(plugin)
            except PluginLoadError as e:
                logger.warning("Failed to load plugin '%s' for profile '%s': %s", path, profile_id, e)

        self._profile_plugins[profile_id] = plugins
        logger.info("Loaded %d plugins for profile '%s'", len(plugins), profile_id)
        return plugins

    def get_for_profile(self, profile_id: str) -> list[BasePlugin]:
        """Get loaded plugins for a profile."""
        return self._profile_plugins.get(profile_id, [])

    def unload_all(self) -> None:
        self._instances.clear()
        self._profile_plugins.clear()

    async def run_hook(self, profile_id: str, hook_name: str, *args, **kwargs):
        """Run a hook across all plugins for a profile. Returns the first arg modified."""
        plugins = self.get_for_profile(profile_id)
        result = args[0] if args else kwargs.get("context", {})
        for plugin in plugins:
            hook = getattr(plugin, hook_name, None)
            if not hook:
                continue
            try:
                if args:
                    result = await hook(*args)
                else:
                    result = await hook(**kwargs)
            except Exception as e:
                logger.error("Plugin '%s' hook '%s' failed: %s", plugin.name, hook_name, e)
        return result
