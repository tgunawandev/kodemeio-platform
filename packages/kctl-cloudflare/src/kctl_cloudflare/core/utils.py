"""Shared utilities for kctl-cloudflare."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from kctl_cloudflare.core.callbacks import AppContext


def human_size(nbytes: int | float) -> str:
    """Format bytes as human-readable size (B, KB, MB, GB, TB, PB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def mask_token(token: str) -> str:
    """Mask a token for display, showing first 4 and last 4 chars."""
    if not token:
        return "[dim]not set[/dim]"
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * max(0, len(token) - 8)}{token[-4:]}"


def status_color(status: str) -> str:
    """Return Rich markup for common Cloudflare statuses."""
    colors: dict[str, str] = {
        "active": "[green]active[/green]",
        "healthy": "[green]healthy[/green]",
        "pending": "[yellow]pending[/yellow]",
        "initializing": "[yellow]initializing[/yellow]",
        "moved": "[dim]moved[/dim]",
        "deactivated": "[red]deactivated[/red]",
        "deleted": "[red]deleted[/red]",
        "inactive": "[dim]inactive[/dim]",
    }
    return colors.get(status.lower(), status)


def tunnel_status_color(status: str) -> str:
    """Return Rich markup for tunnel connection statuses."""
    colors: dict[str, str] = {
        "healthy": "[green]healthy[/green]",
        "degraded": "[yellow]degraded[/yellow]",
        "down": "[red]down[/red]",
        "inactive": "[dim]inactive[/dim]",
    }
    return colors.get(status.lower(), status)


def resolve_zone(c: AppContext, zone: str | None) -> str:
    """Resolve zone name, defaulting to the first available zone."""
    if not zone:
        zones = c.client.get("/zones")
        if isinstance(zones, list) and zones:
            zone = zones[0].get("name", "")
    if not zone:
        c.output.error("No zone specified and no zones found")
        raise typer.Exit(1)
    return zone


def require_account(c: AppContext) -> str:
    """Return account ID or exit with error."""
    acct = c.client.account_id
    if not acct:
        c.output.error("Account ID not configured")
        raise typer.Exit(1)
    return acct
