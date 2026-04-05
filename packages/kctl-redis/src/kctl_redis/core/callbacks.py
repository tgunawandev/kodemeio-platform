"""Typer global callback and shared context for kctl-redis.

Subclasses AppContextBase from kctl-lib, adding Redis-specific
properties (client, host/port/user/password/db overrides).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_redis.core.client import RedisClient
from kctl_redis.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Redis-specific application context."""

    host_override: str | None = None
    port_override: int | None = None
    user_override: str | None = None
    password_override: str | None = None
    db_override: int | None = None
    _client: RedisClient | None = field(default=None, repr=False)

    @property
    def client(self) -> RedisClient:
        if self._client is None:
            config = resolve_connection(
                profile_name=self.profile,
                host_override=self.host_override,
                port_override=self.port_override,
                user_override=self.user_override,
                password_override=self.password_override,
                db_override=self.db_override,
            )
            self._client = RedisClient(config=config)
            self._client.connect()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
