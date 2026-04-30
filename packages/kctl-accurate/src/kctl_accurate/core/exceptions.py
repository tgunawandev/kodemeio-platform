"""Translate accurate-sdk exceptions to kctl_lib.KctlError subclasses.

Centralizes the exit-code contract:
    0 = success
    1 = command-level failure / API s=false / pagination cap exceeded
    2 = config error (handled where it's raised, not here)
    3 = network/HTTP 5xx error
    4 = auth error (401/403)
    5 = rate-limit exhaustion (429 after retries)

Exit codes are produced by ``kctl_lib.handle_cli_error`` based on the
KctlError subclass.
"""

from __future__ import annotations

import httpx
from accurate_sdk.exceptions import (
    AccurateAPIError,
    AccurateSDKError,
    PaginationLimitExceeded,
)
from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    KctlError,
    NotFoundError,
)
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


def translate(exc: BaseException) -> KctlError:
    """Convert any exception coming out of accurate-sdk into a KctlError."""
    if isinstance(exc, KctlError):
        return exc

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        body = exc.response.text or ""
        if code in (401, 403):
            return AuthenticationError(f"Accurate auth failed (HTTP {code}): {body[:200]}")
        if code == 404:
            return NotFoundError("record", body[:80] or "unknown")
        if code == 429:
            return APIError(status_code=429, detail=f"Accurate rate limit exhausted: {body[:200]}")
        return APIError(status_code=code, detail=body[:200])

    if isinstance(exc, httpx.RequestError):
        try:
            url = str(exc.request.url)
        except RuntimeError:
            url = "(unknown)"
        return KctlConnectionError(url, exc)

    if isinstance(exc, AccurateAPIError):
        return APIError(detail=str(exc))

    if isinstance(exc, PaginationLimitExceeded):
        return APIError(detail=str(exc))

    if isinstance(exc, AccurateSDKError):
        return APIError(detail=str(exc))

    return APIError(detail=f"{type(exc).__name__}: {exc}")
