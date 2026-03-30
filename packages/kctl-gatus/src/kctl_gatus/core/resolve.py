"""Utility helpers for resolving Gatus endpoint keys.

Gatus uses a composite key format: group_name (encoded as URL path).
The key for an endpoint is typically: {group}_{name} with spaces
replaced by underscores and URL-encoded.
"""

from __future__ import annotations

import urllib.parse


def encode_endpoint_key(group: str, name: str) -> str:
    """Encode a group/name pair into a Gatus API endpoint key.

    Gatus API expects the key as: {group}_{name}
    where both parts are URL-encoded.
    """
    raw_key = f"{group}_{name}"
    return urllib.parse.quote(raw_key, safe="")


def decode_endpoint_key(key: str) -> tuple[str, str]:
    """Decode a Gatus endpoint key into (group, name).

    Returns ('', key) if no group separator found.
    """
    decoded = urllib.parse.unquote(key)
    parts = decoded.split("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", decoded


def format_duration_ms(duration_ms: int | float) -> str:
    """Format a duration in milliseconds to a human-readable string."""
    if duration_ms < 1:
        return "<1ms"
    if duration_ms < 1000:
        return f"{int(duration_ms)}ms"
    seconds = duration_ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    return f"{minutes:.1f}m"


def format_uptime_percent(uptime: float) -> str:
    """Format an uptime ratio (0.0 - 1.0) as a percentage string."""
    pct = uptime * 100
    if pct >= 99.99:
        return "100.0%"
    return f"{pct:.2f}%"


def status_icon(success: bool) -> str:
    """Return a Rich-formatted status indicator."""
    if success:
        return "[green]UP[/green]"
    return "[red]DOWN[/red]"


def uptime_color(uptime: float) -> str:
    """Return Rich color based on uptime percentage."""
    pct = uptime * 100
    if pct >= 99.9:
        return "green"
    if pct >= 99.0:
        return "yellow"
    return "red"
