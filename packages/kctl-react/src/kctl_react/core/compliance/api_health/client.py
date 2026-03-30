"""HTTP client for API health checks."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HealthClient:
    base_url: str
    token: str | None = None
    timeout: float = 3.0
    rate_limit: float = 0.2  # seconds between requests
    _last_request: float = field(default=0.0, repr=False)

    def authenticate(self, app_path: Path, app_name: str) -> bool:
        """Try dev-login. Read VITE_DEV_USER/VITE_DEV_PASSWORD from .env if available.

        Fallback: try POST /auth/dev-login with admin/admin.
        Store token if successful. Return True/False.
        """
        username = "admin"
        password = "admin"

        env_file = app_path / ".env"
        if env_file.exists():
            try:
                content = env_file.read_text()
                user_match = re.search(r"VITE_DEV_USER\s*=\s*(.+)", content)
                if user_match:
                    username = user_match.group(1).strip().strip("\"'")
                pass_match = re.search(r"VITE_DEV_PASSWORD\s*=\s*(.+)", content)
                if pass_match:
                    password = pass_match.group(1).strip().strip("\"'")
            except OSError as exc:
                logger.warning("Failed to read .env: %s", exc)

        try:
            resp = httpx.post(
                f"{self.base_url}/auth/dev-login",
                json={"username": username, "password": password},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("data", {}).get("access_token"):
                    self.token = data["data"]["access_token"]
                    return True
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Dev-login failed: %s", exc)

        return False

    def get(self, path: str) -> tuple[int, dict | None, float]:
        """GET endpoint with auth header and rate limiting.

        Returns (status_code, response_body_or_None, elapsed_seconds).
        Handles httpx errors gracefully (return 0, None, 0.0 for connection errors).
        """
        self._rate_limit()
        try:
            start = time.monotonic()
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            elapsed = time.monotonic() - start
            self._last_request = time.monotonic()
            try:
                body = resp.json()
            except ValueError:
                body = None
            return resp.status_code, body, elapsed
        except httpx.HTTPError as exc:
            logger.warning("GET %s failed: %s", path, exc)
            return 0, None, 0.0

    def _headers(self) -> dict[str, str]:
        """Return headers with Authorization: Bearer {token} if token set."""
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _rate_limit(self) -> None:
        """Sleep if needed to respect rate_limit interval."""
        if self._last_request > 0:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
