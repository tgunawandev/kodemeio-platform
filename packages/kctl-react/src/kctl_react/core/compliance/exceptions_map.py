"""App-specific exceptions for compliance checks."""

from __future__ import annotations

APP_EXCEPTIONS: dict[str, dict[str, list[str]]] = {
    "mrp": {"skip_providers": ["GPSProvider"]},
    "tpm": {"skip_providers": ["GPSProvider"]},
    "saas": {"skip_providers": ["GPSProvider"]},
    "shop": {"skip_providers": ["GPSProvider"]},
}


def get_skip_providers(app_name: str) -> list[str]:
    """Return list of providers to skip for the given app."""
    return APP_EXCEPTIONS.get(app_name, {}).get("skip_providers", [])
