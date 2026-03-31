"""Shared utility functions."""

from __future__ import annotations


def server_status_color(status: str) -> str:
    """Return Rich color markup for Hetzner server status."""
    colors = {
        "running": "[green]running[/green]",
        "off": "[dim]off[/dim]",
        "starting": "[cyan]starting[/cyan]",
        "stopping": "[yellow]stopping[/yellow]",
        "migrating": "[yellow]migrating[/yellow]",
        "rebuilding": "[yellow]rebuilding[/yellow]",
        "deleting": "[red]deleting[/red]",
        "initializing": "[cyan]initializing[/cyan]",
    }
    return colors.get(status, status)


def action_status_color(status: str) -> str:
    """Return Rich color markup for Hetzner action status."""
    colors = {
        "success": "[green]success[/green]",
        "running": "[cyan]running[/cyan]",
        "error": "[red]error[/red]",
    }
    return colors.get(status, status)


def format_labels(labels: dict | None) -> str:
    """Format a label dict as a comma-separated string."""
    if not labels:
        return "-"
    return ", ".join(f"{k}={v}" for k, v in sorted(labels.items()))


def human_size(size_bytes: int | float) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def mask_token(token: str) -> str:
    """Mask a token for display, showing only first 4 and last 4 chars."""
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def parse_labels(raw: str) -> dict[str, str]:
    """Parse a ``key=val,key=val`` string into a label dict.

    Strips whitespace from keys and values. Skips entries without ``=``
    or with an empty key after stripping.
    """
    result: dict[str, str] = {}
    for kv in raw.split(","):
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        k = k.strip()
        if not k:
            continue
        result[k] = v.strip()
    return result


def parse_price(price_data: dict, key: str = "price_monthly") -> float:
    """Safely parse a price from Hetzner pricing data."""
    try:
        gross = price_data.get(key, {})
        if isinstance(gross, dict):
            return float(gross.get("gross", "0"))
        return float(gross or "0")
    except (ValueError, TypeError, AttributeError):
        return 0.0
