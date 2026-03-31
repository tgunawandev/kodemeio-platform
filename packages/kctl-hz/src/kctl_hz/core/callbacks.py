"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_hz.core.client import HetznerCloudClient, HetznerDnsClient
from kctl_hz.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    token_override: str | None = None
    dns_token_override: str | None = None
    _client: HetznerCloudClient | None = field(default=None, repr=False, init=False)
    _dns_client: HetznerDnsClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> HetznerCloudClient:
        if self._client is None:
            token, _ = resolve_connection(
                profile_name=self.profile,
                token_override=self.token_override,
            )
            self._client = HetznerCloudClient(credential=token)
        return self._client

    @property
    def dns_client(self) -> HetznerDnsClient:
        if self._dns_client is None:
            _, dns_token = resolve_connection(
                profile_name=self.profile,
                dns_token_override=self.dns_token_override,
            )
            self._dns_client = HetznerDnsClient(credential=dns_token)
        return self._dns_client
