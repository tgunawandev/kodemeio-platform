"""Typer global callback and shared context for kctl-gatus.

Subclasses AppContextBase from kctl-lib, adding Gatus-specific
client resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_gatus.core.client import GatusClient
from kctl_gatus.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Gatus-specific application context."""

    url_override: str | None = None
    api_key_override: str | None = None
    _client: GatusClient | None = field(default=None, repr=False)

    @property
    def client(self) -> GatusClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = GatusClient(base_url=url, api_key=api_key)
        return self._client
