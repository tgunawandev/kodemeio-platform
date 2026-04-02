"""Fetch and cache Lucide SVG icons."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

# Lucide icon CDN — MIT licensed, 1400+ icons
LUCIDE_CDN = "https://unpkg.com/lucide-static@latest/icons"

CACHE_DIR = Path.home() / ".cache" / "kodemeio-logo" / "icons"


def get_icon_path(name: str) -> Path:
    """Get cached icon path, downloading if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{name}.svg"

    if cached.exists() and cached.stat().st_size > 0:
        return cached

    url = f"{LUCIDE_CDN}/{name}.svg"
    resp = httpx.get(url, timeout=15, follow_redirects=True)
    if resp.status_code != 200:
        msg = f"Icon '{name}' not found at {url} (HTTP {resp.status_code})"
        raise FileNotFoundError(msg)

    cached.write_text(resp.text)
    return cached


def colorize_svg(svg_path: Path, color: str) -> str:
    """Read an SVG and replace stroke color with the given hex color."""
    svg = svg_path.read_text()
    # Lucide icons use currentColor — replace it
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    svg = svg.replace("currentColor", color)
    return svg


def get_icon_svg(name: str, color: str = "#FFFFFF") -> str:
    """Fetch icon and return colorized SVG string."""
    path = get_icon_path(name)
    return colorize_svg(path, color)


def icon_hash(name: str, color: str) -> str:
    """Generate a short hash for cache busting."""
    raw = f"{name}:{color}"
    return hashlib.md5(raw.encode()).hexdigest()[:8]
