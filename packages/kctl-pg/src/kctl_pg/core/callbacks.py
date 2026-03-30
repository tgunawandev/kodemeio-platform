"""Typer global callback and shared context for kctl-pg.

Subclasses AppContextBase from kctl-common, adding PostgreSQL-specific
properties (client, get_client, host/port/user/password overrides).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_pg.core.client import PostgresClient
from kctl_pg.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """PostgreSQL-specific application context."""

    host_override: str | None = None
    port_override: int | None = None
    user_override: str | None = None
    password_override: str | None = None
    database: str = "postgres"
    _client: PostgresClient | None = field(default=None, repr=False)

    @property
    def client(self) -> PostgresClient:
        if self._client is None:
            config = resolve_connection(
                profile_name=self.profile,
                host_override=self.host_override,
                port_override=self.port_override,
                user_override=self.user_override,
                password_override=self.password_override,
            )
            self._client = PostgresClient(config=config, database=self.database)
            self._client.connect()
        return self._client

    def get_client(self, database: str = "postgres") -> PostgresClient:
        """Get a client connected to a specific database."""
        config = resolve_connection(
            profile_name=self.profile,
            host_override=self.host_override,
            port_override=self.port_override,
            user_override=self.user_override,
            password_override=self.password_override,
        )
        client = PostgresClient(config=config, database=database)
        client.connect()
        return client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
