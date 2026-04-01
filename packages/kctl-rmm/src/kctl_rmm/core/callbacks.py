"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_rmm.core.client import RMMClient
from kctl_rmm.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """RMM-specific application context — extends kctl-lib AppContextBase."""

    url_override: str | None = None
    api_key_override: str | None = None
    _client: RMMClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> RMMClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = RMMClient(base_url=url, api_key=api_key)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
