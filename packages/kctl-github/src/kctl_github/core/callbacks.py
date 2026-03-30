"""Application context for kctl-github."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_github.core.client import GitHubClient
from kctl_github.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)


@dataclass
class AppContext(AppContextBase):
    """kctl-github application context."""

    _client: GitHubClient | None = field(default=None, repr=False)

    @property
    def client(self) -> GitHubClient:
        """Lazy-initialize GitHub API client from active profile config."""
        if self._client is None:
            profile = resolve_active_profile_name(self.profile)
            cfg = get_service_config(profile)
            self._client = GitHubClient(
                credential=cfg.token,
                organization=cfg.organization,
                repo_prefix=cfg.repo_prefix,
            )
        return self._client

    @property
    def config(self) -> ServiceConfig:
        """Get the resolved service config."""
        profile = resolve_active_profile_name(self.profile)
        return get_service_config(profile)
