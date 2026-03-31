"""Typer global callback and shared context for kctl-dokploy.

Subclasses AppContextBase from kctl-lib with Dokploy-specific fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_dokploy.core.client import DokployClient
from kctl_dokploy.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Dokploy-specific application context."""

    debug: bool = False
    url_override: str | None = None
    api_key_override: str | None = None
    _client: DokployClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> DokployClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = DokployClient(base_url=url, api_key=api_key)
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client is not None:
            self._client.close()
