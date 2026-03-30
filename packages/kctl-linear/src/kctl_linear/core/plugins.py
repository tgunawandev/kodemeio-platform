"""Plugin discovery for kctl-linear."""

from kctl_common.plugins import KctlPlugin
from kctl_common.plugins import discover_and_load_plugins as _discover

__all__ = ["KctlPlugin", "discover_and_load_plugins"]

ENTRY_POINT_GROUP = "kctl_linear.plugins"


def discover_and_load_plugins(app):  # noqa: ANN001, ANN201
    """Discover and load kctl-linear plugins."""
    return _discover(app, ENTRY_POINT_GROUP)
