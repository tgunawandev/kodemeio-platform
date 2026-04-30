"""Thin wrapper around accurate_sdk.AccurateClient.

Translates SDK exceptions to KctlError at the boundary so command code
stays kctl-* idiomatic. Validates required config up front (raises
ConfigError) so callers get a clear message instead of a confusing
HTTP 401 later.
"""

from __future__ import annotations

from typing import Any

from accurate_sdk import AccurateClient
from kctl_lib.exceptions import ConfigError

from kctl_accurate.core.config import ServiceConfig
from kctl_accurate.core.exceptions import translate


class AccurateClientWrapper:
    """Wrap AccurateClient to translate exceptions and validate config eagerly."""

    def __init__(self, config: ServiceConfig) -> None:
        missing = []
        if not config.api_token:
            missing.append("api_token")
        if not config.signature_secret:
            missing.append("signature_secret")
        if not config.db_id:
            missing.append("db_id")
        if missing:
            raise ConfigError(
                "Missing required Accurate config: " + ", ".join(missing) + ". Run: kctl-accurate config init"
            )

        self._config = config
        self._client = AccurateClient(
            api_token=config.api_token,
            signature_secret=config.signature_secret,
            host=config.host or None,
        )

    @property
    def raw(self) -> AccurateClient:
        return self._client

    @property
    def config(self) -> ServiceConfig:
        return self._config

    def token_info(self) -> dict[str, Any]:
        """Call the token discovery endpoint and return the raw response dict."""
        try:
            return self._client.token_info()
        except Exception as exc:
            raise translate(exc) from exc

    def db_list(self) -> list[dict[str, Any]]:
        """List all databases accessible with this token."""
        try:
            response = self._client.get("https://account.accurate.id/api/db-list.do")
            return response.get("d") or []
        except Exception as exc:
            raise translate(exc) from exc

    def open_db(self, db_id: int) -> dict[str, Any]:
        """Open a database session and return the session dict."""
        try:
            response = self._client.get(
                "https://account.accurate.id/api/open-db.do",
                params={"id": db_id},
            )
            return response.get("d") or {}
        except Exception as exc:
            raise translate(exc) from exc

    def refresh_token(self) -> dict[str, Any]:
        """Refresh the master API token and return updated info."""
        try:
            return self._client.post("https://account.accurate.id/api/refresh-token.do")
        except Exception as exc:
            raise translate(exc) from exc

    def logout(self) -> dict[str, Any]:
        """Invalidate the current master API token server-side."""
        try:
            return self._client.post("https://account.accurate.id/api/logout.do")
        except Exception as exc:
            raise translate(exc) from exc
