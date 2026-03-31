"""Typer global callback and shared context for kctl-ak.

Subclasses AppContextBase from kctl-lib, adding Authentik-specific
client resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_ak.core.client import AuthentikClient
from kctl_ak.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Authentik-specific application context."""

    url_override: str | None = None
    token_override: str | None = None
    _client: AuthentikClient | None = field(default=None, repr=False)

    @property
    def client(self) -> AuthentikClient:
        if self._client is None:
            url, token = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                token_override=self.token_override,
            )
            self._client = AuthentikClient(base_url=url, credential=token)
        return self._client
