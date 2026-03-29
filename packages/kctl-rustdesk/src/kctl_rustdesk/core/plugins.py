"""Plugin discovery for kctl-rustdesk."""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Protocol

import typer

logger = logging.getLogger(__name__)
ENTRY_POINT_GROUP = "kctl_rustdesk.plugins"


class KctlPlugin(Protocol):
    name: str

    def register(self, app: typer.Typer) -> None: ...


def discover_and_load_plugins(app: typer.Typer) -> list[str]:
    """Discover and load third-party plugins via entry points."""
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
