"""Typer global callback and shared context for kctl-dbgate."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_dbgate.core.client import DBGateClient
from kctl_dbgate.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """kctl-dbgate application context."""

    url_override: str | None = None
    login_override: str | None = None
    password_override: str | None = None
    _client: DBGateClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> DBGateClient:
        if self._client is None:
            url, login, password = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                login_override=self.login_override,
                password_override=self.password_override,
            )
            self._client = DBGateClient(base_url=url, login=login, password=password)
        return self._client
