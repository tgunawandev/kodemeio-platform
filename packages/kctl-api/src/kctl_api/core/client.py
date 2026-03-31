"""REST API client using httpx.

Synchronous client for api-main and ai-main endpoints.
Supports JWT bearer token and API key authentication.

Subclasses :class:`kctl_lib.api_client.APIClient` and keeps dual-auth
(JWT + API key) as a service-specific override of ``_build_auth_header``.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import AuthenticationError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

from kctl_api.core.exceptions import APIError


class ApiClient(APIClient):
    """Synchronous httpx client for Kodemeio REST APIs.

    Extends the kctl-lib base with dual-auth support (JWT bearer token
    **or** API key via ``X-API-Key`` header) and service-specific helpers
    such as ``login``, ``refresh``, ``upload``, and ``stream_sse``.
    """

    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        jwt_token: str = "",
        timeout: float = 30.0,
    ):
        # Resolve the primary credential for the base class.
        # JWT takes precedence; fall back to API key.
        credential = jwt_token or api_key or "none"

        # Store extras *before* super().__init__ since _build_auth_header
        # is called during construction.
        self._api_key = api_key
        self._jwt_token = jwt_token
        self._refresh_token: str = ""

        if not base_url:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No API URL configured. Run: kctl-api config init"),
            )

        super().__init__(
            base_url=base_url,
            credential=credential,
            timeout=timeout,
        )

        # Override follow_redirects (base class doesn't set it)
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._build_auth_header(),
            timeout=timeout,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Auth override — dual-auth (JWT or API key)
    # ------------------------------------------------------------------

    def _build_auth_header(self) -> dict[str, str]:
        """Build authentication headers supporting JWT and API key."""
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    # ------------------------------------------------------------------
    # Error mapping override — use local APIError that wraps httpx.Response
    # ------------------------------------------------------------------

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Override to use kctl-api's APIError (wraps httpx.Response)."""
        try:
            return super()._request(method, endpoint, **kwargs)
        except KctlConnectionError:
            raise
        except AuthenticationError:
            raise
        except Exception as exc:
            # Re-raise kctl-lib APIError as the local response-aware variant
            from kctl_lib.exceptions import APIError as BaseAPIError

            if isinstance(exc, BaseAPIError):
                raise APIError(detail=exc.detail) from exc
            raise

    # ------------------------------------------------------------------
    # Service-specific methods
    # ------------------------------------------------------------------

    def upload(self, path: str, file_path: str, **kwargs: Any) -> Any:
        """Upload a file via multipart POST."""
        url = path
        headers = self._build_auth_header()
        # Remove Content-Type for multipart — httpx sets it automatically
        headers.pop("Content-Type", None)

        with open(file_path, "rb") as f:
            try:
                response = self._client.post(
                    url,
                    headers=headers,
                    files={"file": f},
                    **kwargs,
                )
            except httpx.ConnectError as e:
                raise KctlConnectionError(self._base_url, e) from e

        if response.status_code == 401:
            raise AuthenticationError("Authentication failed.")
        if response.status_code >= 400:
            raise APIError(response)

        return response.json()

    def stream_sse(self, path: str, **kwargs: Any) -> Any:
        """Open an SSE stream. Returns a context manager -- use with ``with``.

        Usage::

            with client.stream_sse("/api/v1/ai/chat/stream") as response:
                for line in response.iter_lines():
                    ...
        """
        url = path
        headers = {**self._build_auth_header(), "Accept": "text/event-stream"}

        try:
            return self._client.stream("GET", url, headers=headers, **kwargs)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._base_url, e) from e

    def login(self, email: str, password: str) -> dict[str, str]:
        """Authenticate and obtain JWT tokens.

        Returns: {"access_token": "...", "refresh_token": "..."}
        """
        data = self.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self._jwt_token = data.get("access_token", "")
        self._refresh_token = data.get("refresh_token", "")
        # Update client headers with new token
        self._client.headers.update(self._build_auth_header())
        return data

    def refresh(self) -> dict[str, str]:
        """Refresh JWT access token using the refresh token."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available. Run: kctl-api auth login")
        data = self.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self._refresh_token},
        )
        self._jwt_token = data.get("access_token", self._jwt_token)
        # Update client headers with new token
        self._client.headers.update(self._build_auth_header())
        return data

    def health_check(self) -> tuple[bool, dict]:
        """Check API health. Returns (is_healthy, details)."""
        try:
            data = self.get("/api/v1/health")
            return data.get("status") == "ok", data
        except Exception as e:
            return False, {"status": "error", "error": str(e)}

    def for_url(self, base_url: str) -> ApiClient:
        """Create a new client for a different base URL (same auth)."""
        return ApiClient(
            base_url=base_url,
            api_key=self._api_key,
            jwt_token=self._jwt_token,
        )
