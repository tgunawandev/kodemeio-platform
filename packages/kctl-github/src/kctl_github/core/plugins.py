"""Plugin discovery for kctl-github."""

from kctl_lib.plugins import KctlPlugin
from kctl_lib.plugins import discover_and_load_plugins as _discover

__all__ = ["KctlPlugin", "discover_and_load_plugins"]

ENTRY_POINT_GROUP = "kctl_github.plugins"


def discover_and_load_plugins(app):  # noqa: ANN001, ANN201
    """Discover and load kctl-github plugins."""
    return _discover(app, ENTRY_POINT_GROUP)
