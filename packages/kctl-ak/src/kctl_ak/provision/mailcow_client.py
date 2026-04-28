"""Lightweight Mailcow API client for provisioning operations only.

Only supports: check mailbox exists, create, enable, disable.
For full Mailcow management use kctl-mailcow.
"""

from __future__ import annotations

import secrets
from typing import Any

import httpx


class MailcowProvisionClient:
    """Minimal Mailcow client for provisioning chain."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 15.0,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        base = api_url.rstrip("/")
        kwargs: dict[str, Any] = {
            "base_url": f"{base}/api/v1",
            "headers": {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            "timeout": timeout,
        }
        if _transport is not None:
            kwargs["transport"] = _transport
        self._client = httpx.Client(**kwargs)

    def mailbox_exists(self, email: str) -> bool:
        """Check if a mailbox exists."""
        resp = self._client.get(f"/get/mailbox/{email}")
        data = resp.json()
        return isinstance(data, list) and len(data) > 0

    def get_mailbox(self, email: str) -> dict[str, Any] | None:
        """Get mailbox details, or None if not found."""
        resp = self._client.get(f"/get/mailbox/{email}")
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return None

    def create_mailbox(
        self,
        email: str,
        name: str,
        quota: int = 1073741824,
    ) -> bool:
        """Create a new mailbox with a random password (user sets via AK recovery)."""
        local, domain = email.split("@", 1)
        password = secrets.token_urlsafe(32)
        payload = {
            "local_part": local,
            "domain": domain,
            "name": name,
            "password": password,
            "password2": password,
            "quota": quota // (1024 * 1024),  # Mailcow expects MB
            "active": "1",
            "force_pw_update": "1",
            "tls_enforce_in": "1",
            "tls_enforce_out": "1",
            "authsource": "generic-oidc",
        }
        resp = self._client.post("/add/mailbox", json=payload)
        result = resp.json()
        if isinstance(result, list) and result:
            return result[0].get("type") == "success"
        return False

    def disable_mailbox(self, email: str) -> bool:
        """Disable a mailbox (mail still received, can't login)."""
        payload = {"attr": {"active": "0"}, "items": [email]}
        resp = self._client.post("/edit/mailbox", json=payload)
        result = resp.json()
        if isinstance(result, list) and result:
            return result[0].get("type") == "success"
        return False

    def enable_mailbox(self, email: str) -> bool:
        """Re-enable a disabled mailbox."""
        payload = {"attr": {"active": "1"}, "items": [email]}
        resp = self._client.post("/edit/mailbox", json=payload)
        result = resp.json()
        if isinstance(result, list) and result:
            return result[0].get("type") == "success"
        return False
