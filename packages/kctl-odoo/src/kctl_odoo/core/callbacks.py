"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_odoo.core.client import OdooClient
from kctl_odoo.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Shared application context passed through Typer's ctx.obj."""

    url_override: str | None = None
    api_key_override: str | None = None
    database_override: str | None = None
    username_override: str | None = None
    _client: OdooClient | None = field(default=None, repr=False)

    @property
    def client(self) -> OdooClient:
        if self._client is None:
            url, database, username, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
                database_override=self.database_override,
                username_override=self.username_override,
            )
            self._client = OdooClient(
                base_url=url,
                database=database,
                username=username,
                api_key=api_key,
            )
        return self._client

    def get_client(self, database: str) -> OdooClient:
        """Return a client for a different database on the same server."""
        return self.client.for_database(database)

    def close(self) -> None:
        """Close the underlying HTTP client if it was initialised."""
        if self._client is not None:
            self._client.close()
