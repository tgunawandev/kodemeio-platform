"""Plugin discovery and loading via entry points.

Third-party packages can register kctl-cf plugins by declaring an entry
point in the ``kctl_cf.plugins`` group.  Each entry point must resolve to a
class that implements :class:`KctlPlugin`.

Example ``pyproject.toml`` snippet for a plugin package::

    [project.entry-points."kctl_cf.plugins"]
    my_plugin = "my_package.plugin:MyPlugin"
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Protocol

import typer

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "kctl_cf.plugins"


class KctlPlugin(Protocol):
    """Interface that kctl-cf plugins must implement."""

    name: str

    def register(self, app: typer.Typer) -> None:
        """Register commands/sub-apps with the main Typer application."""
        ...


def discover_and_load_plugins(app: typer.Typer) -> list[str]:
    """Discover plugins via entry points and register them.

    Returns a list of successfully loaded plugin names.
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
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load plugin %s: %s", ep.name, e)

    return loaded
