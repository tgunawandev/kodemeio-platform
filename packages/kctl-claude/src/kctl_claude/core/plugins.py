"""Plugin discovery for kctl-claude."""

from kctl_common.plugins import KctlPlugin, discover_and_load_plugins

ENTRY_POINT_GROUP = "kctl_claude.plugins"

__all__ = ["ENTRY_POINT_GROUP", "KctlPlugin", "discover_and_load_plugins"]
