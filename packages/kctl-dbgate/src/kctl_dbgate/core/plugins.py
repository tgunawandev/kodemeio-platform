"""Plugin discovery for kctl-dbgate."""

from kctl_lib.plugins import KctlPlugin
from kctl_lib.plugins import discover_and_load_plugins as _discover

__all__ = ["KctlPlugin", "discover_and_load_plugins"]

ENTRY_POINT_GROUP = "kctl_dbgate.plugins"


def discover_and_load_plugins(app):  # noqa: ANN001, ANN201
    """Discover and load kctl-dbgate plugins."""
    return _discover(app, ENTRY_POINT_GROUP)
