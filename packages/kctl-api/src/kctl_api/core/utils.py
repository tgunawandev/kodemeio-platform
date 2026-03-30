"""Shared utility functions."""

from __future__ import annotations

from pathlib import Path

# Known apps in the kodemeio-fastapi monorepo
KNOWN_APPS: dict[str, dict[str, str]] = {
    "api-main": {"type": "API", "port": "8000", "module": "kodemeio_api_main"},
    "ai-main": {"type": "AI API", "port": "8010", "module": "kodemeio_ai_main"},
    "odoo-mm": {"type": "Integration", "port": "8003", "module": "kodemeio_odoo_mm"},
    "plane-mm": {"type": "Integration", "port": "8004", "module": "kodemeio_plane_mm"},
    "webhook-github": {"type": "Webhook", "port": "8005", "module": "kodemeio_webhook_github"},
    "webhook-chatwoot": {"type": "Webhook", "port": "8006", "module": "kodemeio_webhook_chatwoot"},
    "events-sync": {"type": "Events", "port": "", "module": "kodemeio_events_sync"},
    "agent-main": {"type": "Agent", "port": "", "module": "kodemeio_agent_main"},
    "etl-main": {"type": "ETL", "port": "", "module": "kodemeio_etl_main"},
    "mcp-main": {"type": "MCP", "port": "", "module": "kodemeio_mcp_main"},
    "scheduler-main": {"type": "Scheduler", "port": "", "module": "kodemeio_scheduler_main"},
    "stream-main": {"type": "Stream", "port": "8002", "module": "kodemeio_stream_main"},
    "ctl-main": {"type": "CLI", "port": "", "module": "kodemeio_cli_main"},
    "tenant-ai-main": {"type": "Tenant AI", "port": "", "module": "kodemeio_tenant_ai_main"},
}


def service_status_color(status: str) -> str:
    """Return Rich color markup for service status."""
    colors = {
        "running": "[green]running[/green]",
        "healthy": "[green]healthy[/green]",
        "unhealthy": "[red]unhealthy[/red]",
        "stopped": "[dim]stopped[/dim]",
        "starting": "[yellow]starting[/yellow]",
        "error": "[red]error[/red]",
        "ok": "[green]ok[/green]",
    }
    return colors.get(status.lower(), status)


def role_color(role: str) -> str:
    """Return Rich color markup for user role."""
    colors = {
        "admin": "[bold red]admin[/bold red]",
        "user": "[cyan]user[/cyan]",
    }
    return colors.get(role.lower(), role)


def tier_color(tier: str) -> str:
    """Return Rich color markup for user tier."""
    colors = {
        "admin": "[bold red]admin[/bold red]",
        "premium": "[bold yellow]premium[/bold yellow]",
        "user": "[cyan]user[/cyan]",
        "free": "[dim]free[/dim]",
    }
    return colors.get(tier.lower(), tier)


def find_project_root() -> Path:
    """Find the kodemeio-fastapi project root.

    Resolution order:
    1. Walk up from CWD looking for markers (pyproject.toml with kodemeio-fastapi, docker-compose.yml + apps/)
    2. Read ``project_root`` from config profile (~/.config/kodemeio/config.yaml)
    3. Fall back to CWD
    """
    # 1. CWD walk (fast, no config I/O)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if 'name = "kodemeio-fastapi"' in content:
                    return parent
            except Exception:
                pass
        if (parent / "docker-compose.yml").exists() and (parent / "apps").is_dir():
            return parent

    # 2. Config profile fallback
    try:
        from kctl_api.core.config import get_project_root_from_config

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


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret string, showing only the last N characters."""
    if not value or len(value) <= show_chars:
        return "***"
    return f"***{value[-show_chars:]}"
