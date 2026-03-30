"""Shared utility functions for kctl-dokploy.

Formatters, status helpers, and common transformations reused across commands.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime


def status_icon(status: str) -> str:
    """Return a Rich-colored status icon for a Dokploy status string."""
    s = status.lower()
    if s in ("done", "running", "active", "healthy"):
        return "[green]\u25cf[/green]"
    if s in ("error", "failed"):
        return "[red]\u25cf[/red]"
    if s in ("stopped", "exited"):
        return "[yellow]\u25cf[/yellow]"
    return "[blue]\u25cf[/blue]"


def fmt_status(status: str) -> str:
    """Return a Rich-colored status string with icon."""
    return f"{status_icon(status)} {status}"


def human_size(size_bytes: int | float) -> str:
    """Convert bytes to human-readable string (KB, MB, GB, TB)."""
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{int(size_bytes)} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} EB"


def fmt_duration(seconds: float) -> str:
    """Format seconds into human-readable duration (e.g., '2m 30s', '1h 5m')."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s" if s > 0 else f"{m}m"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m" if m > 0 else f"{h}h"


def fmt_timestamp(iso_str: str | None) -> str:
    """Format an ISO timestamp to a human-friendly relative or absolute string."""
    if not iso_str:
        return "-"
    try:
        # Parse ISO format (handle various formats)
        cleaned = re.sub(r"Z$", "+00:00", iso_str)
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        now = datetime.now(tz=UTC)
        delta = now - dt

        total_seconds = delta.total_seconds()
        if total_seconds < 0:
            return iso_str[:19]
        if total_seconds < 60:
            return "just now"
        if total_seconds < 3600:
            return f"{int(total_seconds // 60)}m ago"
        if total_seconds < 86400:
            return f"{int(total_seconds // 3600)}h ago"
        if total_seconds < 604800:
            return f"{int(total_seconds // 86400)}d ago"
        return dt.strftime("%b %d, %H:%M")
    except (ValueError, TypeError):
        return str(iso_str)[:19] if iso_str else "-"


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text to max_len, appending '...' if truncated."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def strip_rich_markup(text: str) -> str:
    """Remove Rich markup tags from text."""
    return re.sub(r"\[/?[^\]]*\]", "", text)
