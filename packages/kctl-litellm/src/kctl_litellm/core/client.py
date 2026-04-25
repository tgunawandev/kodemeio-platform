"""LiteLLM HTTP client — communicates with LiteLLM proxy API.

All API paths route through the LiteLLM proxy:
  - Health:   /health, /health/liveliness
  - Models:   /v1/models, /model/info
  - Keys:     /key/generate, /key/info, /key/update, /key/delete
  - Teams:    /team/new, /team/list, /team/update, /team/delete
  - Budgets:  /budget/new, /budget/list
  - Spend:    /global/spend/logs, /user/daily/activity

Authentication uses:
  - Authorization: Bearer <master_key>
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

from kctl_litellm.core.exceptions import (
    APIError,
    AuthError,
    ConnectionError,
)


class LiteLLMClient:
    """Synchronous HTTP client for LiteLLM proxy API."""

    def __init__(
        self,
        base_url: str,
        master_key: str,
        timeout: float = 30.0,
    ) -> None:
        if not base_url or not base_url.strip():
            raise AuthError("No LiteLLM URL configured. Run: kctl-litellm config add <name> --url <url>")
        if not master_key or not master_key.strip():
            raise AuthError("No master key configured. Run: kctl-litellm config add <name> --master-key <key>")

        self._base_url = base_url.rstrip("/")
        self._master_key = master_key
        self._timeout = timeout

        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        }

        self._client = httpx.Client(
            headers=self._headers,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Core request helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request, raising appropriate errors on failure."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        self._log_debug(f"{method.upper()} {url}")

        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            raise ConnectionError(host=self._base_url, cause=exc) from exc
        except httpx.TimeoutException as exc:
            raise APIError(status_code=0, endpoint=url, message=f"Timeout: {exc}") from exc

        if response.status_code == 401:
            raise AuthError(f"Authentication failed for {url}. Check your master key.")
        if response.status_code >= 400:
            message = self._extract_error(response)
            raise APIError(status_code=response.status_code, endpoint=url, message=message)

        return response

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request returning parsed JSON."""
        return self._request("GET", path, params=params).json()

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """POST request returning parsed JSON."""
        return self._request("POST", path, json=json).json()

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        """Extract a human-readable error from the response body."""
        try:
            data = response.json()
            if isinstance(data, dict):
                for key in ("message", "error_description", "error", "detail", "msg"):
                    if key in data:
                        return str(data[key])
        except (ValueError, KeyError, TypeError):
            pass
        return response.text[:200] if response.text else f"HTTP {response.status_code}"

    @staticmethod
    def _log_debug(msg: str) -> None:
        if os.environ.get("KCTL_DEBUG"):
            print(f"[DEBUG] {msg}", file=sys.stderr)  # noqa: T201

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_liveliness(self) -> dict[str, Any]:
        """Check liveness (no auth required)."""
        url = f"{self._base_url}/health/liveliness"
        self._log_debug(f"GET {url}")
        try:
            response = httpx.get(url, timeout=self._timeout)
        except httpx.ConnectError as exc:
            raise ConnectionError(host=self._base_url, cause=exc) from exc
        except httpx.TimeoutException as exc:
            raise APIError(status_code=0, endpoint=url, message=f"Timeout: {exc}") from exc
        return response.json()

    def health_check(self) -> dict[str, Any]:
        """Full health check (auth required)."""
        return self._get("/health")

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def list_models(self) -> list[dict[str, Any]]:
        """List available models via /v1/models."""
        data = self._get("/v1/models")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else []

    def model_info(self) -> list[dict[str, Any]]:
        """Get model info with pricing via /model/info."""
        data = self._get("/model/info")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------

    def generate_key(self, **kwargs: Any) -> dict[str, Any]:
        """Generate a virtual key via POST /key/generate."""
        return self._post("/key/generate", json=kwargs)

    def get_key_info(self, key: str) -> dict[str, Any]:
        """Get key information via GET /key/info."""
        return self._get("/key/info", params={"key": key})

    def list_keys(self) -> list[dict[str, Any]]:
        """List all keys via GET /key/list."""
        data = self._get("/key/list")
        if isinstance(data, dict) and "keys" in data:
            return data["keys"]
        return data if isinstance(data, list) else []

    def update_key(self, key: str, **kwargs: Any) -> dict[str, Any]:
        """Update a key via POST /key/update."""
        payload = {"key": key, **kwargs}
        return self._post("/key/update", json=payload)

    def delete_key(self, keys: list[str]) -> dict[str, Any]:
        """Delete key(s) via POST /key/delete."""
        return self._post("/key/delete", json={"keys": keys})

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def create_team(self, **kwargs: Any) -> dict[str, Any]:
        """Create a team via POST /team/new."""
        return self._post("/team/new", json=kwargs)

    def list_teams(self) -> list[dict[str, Any]]:
        """List all teams via GET /team/list."""
        data = self._get("/team/list")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "teams" in data:
            return data["teams"]
        return []

    def update_team(self, team_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update a team via POST /team/update."""
        payload = {"team_id": team_id, **kwargs}
        return self._post("/team/update", json=payload)

    def delete_team(self, team_ids: list[str]) -> dict[str, Any]:
        """Delete team(s) via POST /team/delete."""
        return self._post("/team/delete", json={"team_ids": team_ids})

    # ------------------------------------------------------------------
    # Budgets
    # ------------------------------------------------------------------

    def create_budget(self, **kwargs: Any) -> dict[str, Any]:
        """Create a budget via POST /budget/new."""
        return self._post("/budget/new", json=kwargs)

    def list_budgets(self) -> list[dict[str, Any]]:
        """List all budgets via GET /budget/list."""
        data = self._get("/budget/list")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "budgets" in data:
            return data["budgets"]
        return []

    # ------------------------------------------------------------------
    # Spend
    # ------------------------------------------------------------------

    def spend_logs(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get spend logs via GET /global/spend/logs."""
        data = self._get("/global/spend/logs", params=kwargs or None)
        if isinstance(data, list):
            return data
        return []

    def daily_activity(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Get daily activity via GET /user/daily/activity."""
        return self._get("/user/daily/activity", params={"start_date": start_date, "end_date": end_date})

    # ------------------------------------------------------------------
    # Context manager + cleanup
    # ------------------------------------------------------------------

    def __enter__(self) -> LiteLLMClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
