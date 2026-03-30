"""Shared utility functions."""

from __future__ import annotations

from pathlib import Path

# Known FastAPI PWA apps and their API base paths
KNOWN_APPS: dict[str, str] = {
    "sfa": "/sfa/api",
    "lfa": "/lfa/api",
    "shop": "/shop/api",
    "wms": "/wms/api",
    "bia": "/bia/api",
    "eam": "/asset/api",
    "mrp": "/mrp/api",
    "hrm": "/hrm/api",
    "tpm": "/tpm/api",
    "dms": "/dms/api",
    "saas": "/saas/api",
}


def module_state_color(state: str) -> str:
    """Return Rich color markup for Odoo module state."""
    colors = {
        "installed": "[green]installed[/green]",
        "uninstalled": "[dim]uninstalled[/dim]",
        "to upgrade": "[yellow]to upgrade[/yellow]",
        "to install": "[cyan]to install[/cyan]",
        "to remove": "[red]to remove[/red]",
    }
    return colors.get(state, state)


def check_module_installed(client: object, module_name: str) -> bool:
    """Check if an Odoo module is installed.

    Returns ``True`` if *module_name* is in ``installed`` state,
    ``False`` otherwise (including when the RPC call fails).
    """
    try:
        return (
            client.search_count(  # type: ignore[union-attr]
                "ir.module.module",
                [("name", "=", module_name), ("state", "=", "installed")],
            )
            > 0
        )
    except Exception:
        return False


def find_project_root() -> Path:
    """Find the Odoo project root.

    Resolution order:
    1. Walk up from CWD looking for markers (docker-compose.yml, src/private/)
    2. Read ``project_root`` from config profile (~/.config/kodemeio/config.yaml)
    3. Fall back to CWD
    """
    # 1. CWD walk (fast, no config I/O)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "docker-compose.yml").exists() or (parent / "src" / "private").is_dir():
            return parent

    # 2. Config profile fallback
    try:
        from kctl_odoo.core.config import get_project_root_from_config

        config_root = get_project_root_from_config()
        if config_root is not None:
            return config_root
    except Exception:
        pass

    # 3. CWD fallback
    return cwd


def human_size(size_bytes: int | float) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
