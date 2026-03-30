"""Plugin discovery system for kctl-dokploy.

Third-party packages can extend the CLI by declaring entry points in their
pyproject.toml under the group ``kctl_dokploy.plugins``.

Example plugin registration in pyproject.toml:

    [project.entry-points."kctl_dokploy.plugins"]
    my_plugin = "my_package.plugin:MyPlugin"

The plugin class must implement the KctlPlugin protocol.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Protocol

import typer

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "kctl_dokploy.plugins"


class KctlPlugin(Protocol):
    """Interface that kctl-dokploy plugins must implement."""

    name: str

    def register(self, app: typer.Typer) -> None:
        """Register commands with the main Typer app."""
        ...


def discover_and_register_plugins(app: typer.Typer) -> list[str]:
    """Discover and load plugins via entry points.

    Returns list of successfully loaded plugin names.
    """
    loaded: list[str] = []
    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:
        return loaded

    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            plugin.register(app)
            loaded.append(ep.name)
            logger.debug("Loaded plugin: %s", ep.name)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", ep.name, e)
    return loaded
