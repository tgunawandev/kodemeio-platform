"""Translate accurate-sdk exceptions to kctl_lib.KctlError subclasses.

The KctlError subclass carries the *intended* exit code per the
spec's contract:
    AuthenticationError → exit 4 (auth/signature failure)
    APIError(429)       → exit 5 (rate-limit exhaustion)
    KctlConnectionError → exit 3 (network/host unreachable)
    APIError (other)    → exit 1 (command-level failure)
    NotFoundError       → exit 1

kctl_lib 0.4.0's handle_cli_error currently exits 1 for every
KctlError; per-code routing requires either a kctl_lib upgrade or
per-command _run() overrides. Carrying the right subclass here lets
that future upgrade activate without re-touching every command.
"""

from __future__ import annotations

import httpx
from accurate_sdk.exceptions import (
    AccurateAPIError,
    AccurateRateLimitError,
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


def translate(exc: Exception) -> KctlError:
    """Convert any exception coming out of accurate-sdk into a KctlError."""
    if isinstance(exc, KctlError):
        return exc

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        body = exc.response.text or ""
        if code in (401, 403):
            return AuthenticationError(f"Accurate auth failed (HTTP {code}): {body[:200]}")
        if code == 404:
            return NotFoundError("record", body[:200] or "unknown")
        if code == 429:
            return APIError(status_code=429, detail=f"Accurate rate limit exhausted: {body[:200]}")
        return APIError(status_code=code, detail=body[:200])

    if isinstance(exc, httpx.RequestError):
        try:
            url = str(exc.request.url)
        except RuntimeError:
            url = "(unknown)"
        return KctlConnectionError(url, exc)

    if isinstance(exc, AccurateRateLimitError):
        return APIError(status_code=429, detail=f"Accurate rate limit exhausted: {exc}")

    if isinstance(exc, AccurateAPIError):
        return APIError(detail=str(exc))

    if isinstance(exc, PaginationLimitExceeded):
        return APIError(detail=str(exc))

    if isinstance(exc, AccurateSDKError):
        return APIError(detail=str(exc))

    return APIError(detail=f"{type(exc).__name__}: {exc}")
