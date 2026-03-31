"""Plugin discovery — delegates to kctl-lib with kctl-odoo entry point group."""

from __future__ import annotations

import importlib.metadata
import logging

from kctl_lib.plugins import KctlPlugin

__all__ = ["KctlPlugin", "discover_and_load_plugins"]

ENTRY_POINT_GROUP = "kctl_odoo.plugins"

logger = logging.getLogger(__name__)


def discover_and_load_plugins(app):  # noqa: ANN001, ANN201
    """Discover and load kctl-odoo plugins via entry points."""
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
