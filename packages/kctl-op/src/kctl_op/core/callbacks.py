"""Shared application context for kctl-op.

Subclasses AppContextBase from kctl-lib, adding 1Password-specific
fields: vault override, token override, lazy client and service config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_op.core.client import OnePasswordClient
from kctl_op.core.config import ServiceConfig, resolve_config


@dataclass
class AppContext(AppContextBase):
    """1Password-specific application context."""

    vault_override: str | None = None
    token_override: str | None = None
    _client: OnePasswordClient | None = field(default=None, repr=False)
    _service_config: ServiceConfig | None = field(default=None, repr=False)

    @property
    def service_config(self) -> ServiceConfig:
        if self._service_config is None:
            self._service_config = resolve_config(
                profile_name=self.profile,
                vault_override=self.vault_override,
                token_override=self.token_override,
            )
        return self._service_config

    @property
    def client(self) -> OnePasswordClient:
        if self._client is None:
            cfg = self.service_config
            self._client = OnePasswordClient(
                vault=cfg.vault,
                token=cfg.service_account_token,
            )
        return self._client
