"""Sentry API client — subclasses kctl-common APIClient."""

from __future__ import annotations

from typing import Any

from kctl_common.api_client import APIClient
from kctl_common.exceptions import AuthenticationError


class SentryClient(APIClient):
    """Synchronous client for Sentry REST API."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/0"

    def __init__(
        self,
        base_url: str = "https://sentry.io",
        auth_token: str = "",
        organization: str = "",
        default_project: str = "",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        if not auth_token:
            raise AuthenticationError("No auth token configured. Run: kctl-sentry config init")
        super().__init__(base_url=base_url, credential=auth_token, timeout=timeout, **kwargs)
        self._organization = organization
        self._default_project = default_project

    @property
    def organization(self) -> str:
        return self._organization

    @property
    def default_project(self) -> str:
        return self._default_project

    def resolve_project(self, project: str | None) -> str:
        """Resolve project slug: explicit arg > default_project config."""
        if project:
            return project
        if self._default_project:
            return self._default_project
        raise AuthenticationError("No project specified and no default_project configured")

    # ------------------------------------------------------------------
    # Convenience: org-scoped endpoints
    # ------------------------------------------------------------------

    def org_get(self, path: str, **kwargs: Any) -> Any:
        """GET /organizations/{org}/{path}."""
        return self.get(f"/organizations/{self._organization}{path}", **kwargs)

    def org_post(self, path: str, **kwargs: Any) -> Any:
        """POST /organizations/{org}/{path}."""
        return self.post(f"/organizations/{self._organization}{path}", **kwargs)

    def org_put(self, path: str, **kwargs: Any) -> Any:
        """PUT /organizations/{org}/{path}."""
        return self.put(f"/organizations/{self._organization}{path}", **kwargs)

    # ------------------------------------------------------------------
    # Convenience: project-scoped endpoints
    # ------------------------------------------------------------------

    def project_get(self, project: str, path: str, **kwargs: Any) -> Any:
        """GET /projects/{org}/{project}/{path}."""
        return self.get(f"/projects/{self._organization}/{project}{path}", **kwargs)

    def project_post(self, project: str, path: str, **kwargs: Any) -> Any:
        """POST /projects/{org}/{project}/{path}."""
        return self.post(f"/projects/{self._organization}/{project}{path}", **kwargs)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_health(self) -> dict[str, Any]:
        """Verify API connectivity by fetching org details."""
        result = self.get(f"/organizations/{self._organization}/")
        return result if isinstance(result, dict) else {}
