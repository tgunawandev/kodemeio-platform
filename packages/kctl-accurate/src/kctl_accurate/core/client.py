"""Thin wrapper around accurate_sdk.AccurateClient.

Translates SDK exceptions to KctlError at the boundary so command code
stays kctl-* idiomatic. Validates required config up front (raises
ConfigError) so callers get a clear message instead of a confusing
HTTP 401 later.
"""

from __future__ import annotations

from typing import Any, cast

from accurate_sdk import AccurateClient
from accurate_sdk.exceptions import AccurateAPIError
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

    @staticmethod
    def _check_s(response: dict[str, Any], endpoint: str) -> dict[str, Any]:
        """Raise AccurateAPIError if response carries s=false.

        Accurate uses a uniform envelope: ``{"s": bool, "d": <payload>}``.
        On failure, ``d`` is a list of human-readable error strings (not the
        success-shape dict), so callers that try ``response["d"].get(...)``
        crash with AttributeError. Centralizing the check here gives a clean
        APIError → exit-code path via the SDK→KctlError translator.
        """
        if not response.get("s", False):
            errors = response.get("d") or []
            if isinstance(errors, list):
                msg = "; ".join(str(e) for e in errors) or "unknown error"
            else:
                msg = str(errors)
            raise AccurateAPIError(f"Accurate API error for {endpoint}: {msg}")
        return response

    def token_info(self) -> dict[str, Any]:
        """Call the token discovery endpoint and return the raw response dict."""
        try:
            response = cast(dict[str, Any], self._client.token_info())
            return self._check_s(response, "api-token.do")
        except Exception as exc:
            raise translate(exc) from exc

    def db_list(self) -> list[dict[str, Any]]:
        """List all databases accessible with this token."""
        try:
            response = self._client.get("https://account.accurate.id/api/db-list.do")
            self._check_s(response, "db-list.do")
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
            self._check_s(response, "open-db.do")
            return response.get("d") or {}
        except Exception as exc:
            raise translate(exc) from exc

    def refresh_token(self) -> dict[str, Any]:
        """Refresh the master API token and return updated info."""
        try:
            response = cast(dict[str, Any], self._client.post("https://account.accurate.id/api/refresh-token.do"))
            return self._check_s(response, "refresh-token.do")
        except Exception as exc:
            raise translate(exc) from exc

    def logout(self) -> dict[str, Any]:
        """Invalidate the current master API token server-side."""
        try:
            response = cast(dict[str, Any], self._client.post("https://account.accurate.id/api/logout.do"))
            return self._check_s(response, "logout.do")
        except Exception as exc:
            raise translate(exc) from exc
