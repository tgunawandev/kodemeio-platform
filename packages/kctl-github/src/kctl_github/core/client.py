"""GitHub API client and gh CLI helper."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from kctl_lib.api_client import APIClient
from kctl_lib.runner import run


class GitHubClient(APIClient):
    """Synchronous GitHub REST API client.

    Subclasses APIClient with GitHub-specific defaults.
    Provides helpers for paginated listing and repo filtering.
    """

    BASE_URL = "https://api.github.com"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def __init__(
        self,
        credential: str = "",
        organization: str = "tgunawandev",
        repo_prefix: str = "kodemeio-",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(credential=credential, timeout=timeout, **kwargs)
        self._organization = organization
        self._repo_prefix = repo_prefix
        # Add Accept header for GitHub API v3
        self._client.headers["Accept"] = "application/vnd.github+json"
        self._client.headers["X-GitHub-Api-Version"] = "2022-11-28"

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated GitHub endpoint.

        GitHub uses Link headers for pagination. This method follows
        ``next`` links up to *max_pages*.
        """
        all_items: list[dict[str, Any]] = []
        _params = dict(params or {})
        _params.setdefault("per_page", 100)

        for _ in range(max_pages):
            response = self._request("GET", endpoint, params=_params)
            data = response.json()
            if isinstance(data, list):
                all_items.extend(data)
            else:
                # Some endpoints return objects with items inside
                break

            # Check for next page via Link header
            link = response.headers.get("link", "")
            if 'rel="next"' not in link:
                break

            # Parse next URL from Link header
            next_url = _parse_next_link(link)
            if not next_url:
                break

            # Extract query params from the next URL for subsequent request
            parsed = urlparse(next_url)
            _params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        return all_items

    # ------------------------------------------------------------------
    # Repo helpers
    # ------------------------------------------------------------------

    def get_repos(self) -> list[dict[str, Any]]:
        """Get all repos matching the configured prefix."""
        repos = self.get_paginated(f"/users/{self._organization}/repos")
        return [r for r in repos if r.get("name", "").startswith(self._repo_prefix)]

    def get_repo(self, name: str) -> dict[str, Any]:
        """Get a single repo by name (short name, not full_name)."""
        return self.get(f"/repos/{self._organization}/{name}")

    @property
    def organization(self) -> str:
        return self._organization

    @property
    def repo_prefix(self) -> str:
        return self._repo_prefix


def _parse_next_link(link_header: str) -> str | None:
    """Parse the 'next' URL from a GitHub Link header."""
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None


def gh_run(args: list[str], check: bool = True) -> str:
    """Run a gh CLI command and return stdout.

    Args:
        args: Arguments to pass to ``gh`` (e.g., ["pr", "view", "123"]).
        check: If True, raise CommandError on non-zero exit.

    Returns:
        The stdout output as a string.
    """
    result = run(["gh", *args], check=check)
    return result.stdout.strip()
