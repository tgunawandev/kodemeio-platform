"""Plugin discovery and loading via Python entry points.

Each kctl-* CLI declares its own entry point group (e.g., "kctl_next.plugins").
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Protocol

import typer

logger = logging.getLogger(__name__)


class KctlPlugin(Protocol):
    """Interface that kctl plugins must implement."""

    name: str

    def register(self, app: typer.Typer) -> None:
        """Register commands/sub-apps with the main Typer application."""
        ...


def discover_and_load_plugins(app: typer.Typer, entry_point_group: str) -> list[str]:
    """Discover plugins via entry points and register them."""
    loaded: list[str] = []
    try:
        eps = importlib.metadata.entry_points(group=entry_point_group)
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
