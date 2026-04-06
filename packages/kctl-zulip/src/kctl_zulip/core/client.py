"""Zulip API client using httpx.

Zulip uses HTTP Basic auth (email:api_key) and REST at /api/v1/.
"""

from __future__ import annotations

import httpx

from kctl_lib.exceptions import AuthenticationError, KctlError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class ZulipAPIError(KctlError):
    """Zulip API error with response details."""

    def __init__(self, response: httpx.Response):
        self.status_code = response.status_code
        self.response = response
        try:
            body = response.json()
            self.detail = body.get("msg", str(body))
        except Exception:
            # Zulip may return HTML for 404s -- extract a short message
            text = response.text or ""
            if "<html" in text.lower():
                self.detail = f"HTTP {self.status_code}"
            else:
                self.detail = text[:200] if text else f"HTTP {self.status_code}"
        super().__init__(f"API error {self.status_code}: {self.detail}")


class ZulipClient:
    """Synchronous httpx client for Zulip API v1."""

    def __init__(self, base_url: str, email: str, api_key: str, timeout: float = 30.0):
        if not base_url:
            raise KctlConnectionError(
                "(not configured)", ValueError("No API URL configured. Run: kctl-zulip config init")
            )
        if not email or not api_key:
            raise AuthenticationError("No email/api_key configured. Run: kctl-zulip config init")

        self._base_url = base_url.rstrip("/")
        self._api_url = self._base_url + "/api/v1"

        self._client = httpx.Client(
            base_url=self._api_url,
            auth=(email, api_key),
            headers={
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def _ensure_path(self, endpoint: str) -> str:
        return endpoint.lstrip("/")

    def _check_response(self, response: httpx.Response) -> None:
        """Check Zulip response for errors. Zulip returns 200 with result=error."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid email/api_key. Check your credentials.")
        if response.status_code == 403:
            raise AuthenticationError("Permission denied. Check your credentials.")
        if response.status_code >= 400:
            raise ZulipAPIError(response)

        # Zulip-specific: 200 with result=error
        if response.content:
            try:
                body = response.json()
                if body.get("result") == "error":
                    raise ZulipAPIError(response)
            except (ValueError, KeyError):
                pass

    def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make a request, raise ZulipAPIError on errors."""
        url = self._ensure_path(endpoint)
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._api_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._api_url, e) from e

        self._check_response(response)
        return response

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        resp = self.request("GET", endpoint, params=params)
        if not resp.content:
            return {}
        return resp.json()

    def post(self, endpoint: str, data: dict | None = None) -> dict:
        """POST with form data (Zulip convention)."""
        resp = self.request("POST", endpoint, data=data)
        if not resp.content:
            return {}
        return resp.json()

    def post_json(self, endpoint: str, data: dict | None = None) -> dict:
        """POST with JSON body."""
        resp = self.request("POST", endpoint, json=data)
        if not resp.content:
            return {}
        return resp.json()

    def patch(self, endpoint: str, data: dict) -> dict:
        resp = self.request("PATCH", endpoint, data=data)
        if not resp.content:
            return {}
        return resp.json()

    def delete(self, endpoint: str) -> dict:
        resp = self.request("DELETE", endpoint)
        if not resp.content:
            return {}
        return resp.json()

    def post_multipart(self, endpoint: str, files: dict, data: dict | None = None) -> dict:
        """POST with multipart form data (for file uploads)."""
        url = self._ensure_path(endpoint)
        try:
            response = self._client.post(url, files=files, data=data)
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._api_url, e) from e
        self._check_response(response)
        if not response.content:
            return {}
        return response.json()

    def check_health(self) -> dict:
        """Check server settings (public endpoint, no auth needed)."""
        try:
            r = httpx.get(f"{self._base_url}/api/v1/server_settings", timeout=5)
            if r.status_code == 200:
                return r.json()
            return {}
        except httpx.HTTPError:
            return {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ZulipClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
