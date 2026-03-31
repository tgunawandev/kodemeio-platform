"""Plugin discovery for kctl-api — thin wrapper over kctl-lib.

Third-party packages register kctl-api plugins via the ``kctl_api.plugins``
entry point group.  Each entry point must resolve to a class implementing
:class:`KctlPlugin`.

Example ``pyproject.toml`` snippet for a plugin package::

    [project.entry-points."kctl_api.plugins"]
    my_plugin = "my_package.plugin:MyPlugin"
"""

from __future__ import annotations

import typer
from kctl_lib.plugins import KctlPlugin
from kctl_lib.plugins import discover_and_load_plugins as _discover

__all__ = ["ENTRY_POINT_GROUP", "KctlPlugin", "discover_and_load_plugins"]

ENTRY_POINT_GROUP = "kctl_api.plugins"


def discover_and_load_plugins(app: typer.Typer) -> list[str]:
    """Discover kctl-api plugins via entry points and register them."""
    return _discover(app, ENTRY_POINT_GROUP)
