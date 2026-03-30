"""Application context for kctl-linear."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_linear.core.client import LinearClient
from kctl_linear.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)
from kctl_linear.core.exceptions import ConfigError


@dataclass
class AppContext(AppContextBase):
    """kctl-linear application context."""

    _client: LinearClient | None = field(default=None, repr=False)

    @property
    def config(self) -> ServiceConfig:
        """Resolve the active profile's service config."""
        profile = resolve_active_profile_name(self.profile)
        return get_service_config(profile)

    @property
    def client(self) -> LinearClient:
        """Lazy-init LinearClient from profile config."""
        if self._client is None:
            cfg = self.config
            if not cfg.api_key:
                raise ConfigError("Linear API key is not configured. Run: kctl-linear config init")
            self._client = LinearClient(api_key=cfg.api_key)
        return self._client

    @property
    def default_team(self) -> str | None:
        """Return the default team key, or None if not set."""
        team = self.config.default_team
        return team if team else None
