"""Async REST API client using httpx.

Mirror of :class:`kctl_api.core.client.ApiClient` with ``async`` methods
and :class:`httpx.AsyncClient` under the hood.

Subclasses :class:`kctl_lib.async_api_client.AsyncAPIClient` and keeps
dual-auth (JWT + API key) as a service-specific override.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from kctl_lib.async_api_client import AsyncAPIClient
from kctl_lib.exceptions import AuthenticationError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

from kctl_api.core.exceptions import APIError


class AsyncApiClient(AsyncAPIClient):
    """Asynchronous httpx client for Kodemeio REST APIs.

    Extends the kctl-lib async base with dual-auth support (JWT bearer
    token **or** API key via ``X-API-Key`` header) and service-specific helpers.
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
        credential = jwt_token or api_key or "none"

        # Store extras *before* super().__init__ since _build_auth_header
        # is called during construction.
        self._api_key = api_key
        self._jwt_token = jwt_token

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

        # Override with follow_redirects (base class doesn't set it)
        self._client = httpx.AsyncClient(
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
    # Error mapping override
    # ------------------------------------------------------------------

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Override to use kctl-api's APIError (wraps httpx.Response)."""
        try:
            return await super()._request(method, endpoint, **kwargs)
        except KctlConnectionError:
            raise
        except AuthenticationError:
            raise
        except Exception as exc:
            from kctl_lib.exceptions import APIError as BaseAPIError

            if isinstance(exc, BaseAPIError):
                raise APIError(detail=exc.detail) from exc
            raise

    # ------------------------------------------------------------------
    # Service-specific methods
    # ------------------------------------------------------------------

    async def health_check(self) -> tuple[bool, dict]:
        """Check API health."""
        try:
            data = await self.get("/api/v1/health")
            return data.get("status") == "ok", data
        except Exception as e:
            return False, {"status": "error", "error": str(e)}


async def async_batch(*coroutines: Any, max_concurrent: int = 10) -> list[Any]:
    """Run multiple async operations with a concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return list(await asyncio.gather(*(bounded(c) for c in coroutines)))
