"""Base async API client with retry, error mapping, and debug logging."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from random import uniform
from typing import Any, Self

import httpx

from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class AsyncAPIClient:
    """Asynchronous base API client for kctl-* CLI tools.

    Subclass and override class attributes to customise per-service::

        class MyAsyncClient(AsyncAPIClient):
            BASE_URL = "https://api.example.com"
            AUTH_HEADER = "Authorization"
            AUTH_PREFIX = "Bearer"
            API_PREFIX = "/v1"
    """

    # Subclass overrides
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"
    API_PREFIX: str = ""
    BASE_URL: str = ""

    def __init__(
        self,
        base_url: str = "",
        credential: str = "",
        timeout: float = 30.0,
        retry_enabled: bool = False,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
        **_kwargs: Any,
    ) -> None:
        if not credential or not credential.strip():
            raise ConfigError("API credential is required")

        resolved_url = base_url or self.BASE_URL
        if not resolved_url:
            raise ConfigError("base_url is required (pass it or set BASE_URL on the class)")

        # Clean trailing slash
        resolved_url = resolved_url.rstrip("/")

        # Append API_PREFIX if not already present
        if self.API_PREFIX and not resolved_url.endswith(self.API_PREFIX.rstrip("/")):
            resolved_url = resolved_url + self.API_PREFIX

        self._base_url = resolved_url
        self._credential = credential
        self._retry_enabled = retry_enabled
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._build_auth_header(),
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _build_auth_header(self) -> dict[str, str]:
        """Build the authentication header dict."""
        if self.AUTH_PREFIX:
            return {self.AUTH_HEADER: f"{self.AUTH_PREFIX} {self._credential}"}
        return {self.AUTH_HEADER: self._credential}

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request with optional retry logic."""
        url = endpoint.lstrip("/")
        attempts = 1 + (self._max_retries if self._retry_enabled else 0)

        last_exc: Exception | None = None
        last_response: httpx.Response | None = None

        for attempt in range(attempts):
            try:
                self._log_debug(f"{method.upper()} {self._base_url}{url}")
                response = await self._client.request(method, url, **kwargs)

                if response.status_code < 400:
                    return response

                # Auth errors — never retry
                if response.status_code in (401, 403):
                    detail = self._map_error(response)
                    raise AuthenticationError(detail)

                # Server errors — retry if enabled
                if response.status_code >= 500 and self._retry_enabled and attempt < attempts - 1:
                    last_response = response
                    await self._sleep_with_jitter(attempt)
                    continue

                # Client errors or final server error
                last_response = response
                break

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if self._retry_enabled and attempt < attempts - 1:
                    await self._sleep_with_jitter(attempt)
                    continue
                raise KctlConnectionError(url=self._base_url, cause=exc) from exc

        # If we broke out of the loop with a response, raise the appropriate error
        if last_response is not None:
            detail = self._map_error(last_response)
            raise APIError(status_code=last_response.status_code, detail=detail)

        # Should not reach here, but handle connection errors after exhausted retries
        if last_exc is not None:
            raise KctlConnectionError(url=self._base_url, cause=last_exc) from last_exc

        raise APIError(detail="Unexpected request state")  # pragma: no cover

    # ------------------------------------------------------------------
    # Response unwrapping
    # ------------------------------------------------------------------

    def _unwrap_response(self, response: httpx.Response) -> Any:
        """Parse the response body. Override for envelope unwrapping."""
        if not response.text.strip():
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_error(response: httpx.Response) -> str:
        """Extract a human-readable error detail from the response."""
        try:
            data = response.json()
            if isinstance(data, dict):
                for key in ("detail", "error", "message"):
                    if key in data:
                        val = data[key]
                        return str(val) if not isinstance(val, str) else val
        except Exception:  # noqa: BLE001
            pass
        return response.text[:200] if response.text else f"HTTP {response.status_code}"

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    async def _sleep_with_jitter(self, attempt: int) -> None:
        """Exponential backoff with full jitter."""
        ceiling = min(self._retry_base_delay * (2**attempt), self._retry_max_delay)
        await asyncio.sleep(uniform(0, ceiling))  # noqa: S311

    # ------------------------------------------------------------------
    # Debug logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_debug(msg: str) -> None:
        """Print debug info to stderr when KCTL_DEBUG is set."""
        if os.environ.get("KCTL_DEBUG"):
            print(f"[DEBUG] {msg}", file=sys.stderr)  # noqa: T201

    # ------------------------------------------------------------------
    # CRUD convenience methods
    # ------------------------------------------------------------------

    async def get(self, endpoint: str, **kwargs: Any) -> Any:
        return self._unwrap_response(await self._request("GET", endpoint, **kwargs))

    async def post(self, endpoint: str, **kwargs: Any) -> Any:
        return self._unwrap_response(await self._request("POST", endpoint, **kwargs))

    async def put(self, endpoint: str, **kwargs: Any) -> Any:
        return self._unwrap_response(await self._request("PUT", endpoint, **kwargs))

    async def patch(self, endpoint: str, **kwargs: Any) -> Any:
        return self._unwrap_response(await self._request("PATCH", endpoint, **kwargs))

    async def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return self._unwrap_response(await self._request("DELETE", endpoint, **kwargs))

    # ------------------------------------------------------------------
    # SSE / tRPC subscription streaming
    # ------------------------------------------------------------------

    async def stream_subscription(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream a tRPC subscription as one log-line-per-string.

        Wire format (Dokploy 0.29 / tRPC v11 SSE, confirmed in Task 1 spike):
          - HTTP GET with ``?input=<url-encoded JSON>`` query param
          - Response Content-Type: text/event-stream
          - Named control events (``connected``, ``return``) are skipped
          - Unnamed data events: ``data: {"json":"<line>"}`` → yield ``"<line>"``
          - ``event: serialized-error`` events: yield ``Error: <message>``

        Raises APIError on 4xx/5xx before the stream opens.
        """
        import json as _json
        from urllib.parse import quote

        input_encoded = quote(_json.dumps(payload), safe="")
        url = f"{endpoint.lstrip('/')}?input={input_encoded}"

        async with self._client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                detail = body.decode(errors="replace")[:500]
                raise APIError(status_code=resp.status_code, detail=detail)

            # Parse SSE: events are separated by blank lines; within an event,
            # ``event: <name>`` (optional, defaults to "message") and one or
            # more ``data: ...`` lines.
            current_event: str = "message"  # SSE default
            data_lines: list[str] = []

            async for raw in resp.aiter_lines():
                line = raw.rstrip("\r")
                if line == "":
                    # End of one event — dispatch it.
                    event_name = current_event
                    data_str = "\n".join(data_lines)
                    current_event = "message"
                    data_lines = []

                    if event_name in ("connected", "return"):
                        continue  # control events; skip

                    if not data_str:
                        continue

                    try:
                        obj = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        yield data_str
                        continue

                    if event_name == "serialized-error":
                        json_val = obj.get("json", {}) if isinstance(obj, dict) else {}
                        msg = json_val.get("message", "unknown error") if isinstance(json_val, dict) else str(json_val)
                        yield f"Error: {msg}"
                        continue

                    # Default / 'message' event — unwrap {"json": "..."} or yield as-is
                    if isinstance(obj, dict) and "json" in obj:
                        val = obj["json"]
                        if isinstance(val, str):
                            yield val
                        else:
                            yield _json.dumps(val)
                    else:
                        yield data_str
                elif line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].lstrip(" "))
                # else: SSE comments (``:foo``) or unknown fields — ignore

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
