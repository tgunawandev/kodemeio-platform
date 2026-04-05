"""Redis client with SSH tunnel support using redis-py.

Connects to remote Redis servers through an SSH tunnel
using sshtunnel + redis-py with connection pooling.
"""

from __future__ import annotations

from typing import Any

import redis

from kctl_lib.ssh_tunnel import SSHTunnel
from kctl_redis.core.config import ServiceConfig
from kctl_redis.core.exceptions import (
    AuthenticationError,
    KctlConnectionError,
    RedisCommandError,
    SSHTunnelError,
)


class RedisClient:
    """Redis client that connects through an SSH tunnel."""

    def __init__(self, config: ServiceConfig):
        if not config.host:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No Redis host configured. Run: kctl-redis config init"),
            )
        if not config.ssh_host:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No SSH host configured. Run: kctl-redis config init"),
            )

        self._config = config
        self._tunnel: SSHTunnel | None = None
        self._redis: redis.Redis | None = None  # type: ignore[type-arg]

    def connect(self) -> None:
        """Open SSH tunnel and connect to Redis."""
        cfg = self._config

        self._tunnel = SSHTunnel(
            ssh_host=cfg.ssh_host,
            ssh_port=cfg.ssh_port,
            ssh_user=cfg.ssh_user,
            ssh_key=cfg.ssh_key,
            remote_host=cfg.host,
            remote_port=cfg.port,
        )
        try:
            self._tunnel.start()
        except Exception as e:
            raise SSHTunnelError(cfg.ssh_host, e) from e

        local_port = self._tunnel.local_port

        try:
            self._redis = redis.Redis(
                host="127.0.0.1",
                port=local_port,
                username=cfg.username if cfg.username != "default" else None,
                password=cfg.password or None,
                db=cfg.db,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
            # Test connection
            self._redis.ping()
        except redis.AuthenticationError as e:
            raise AuthenticationError(f"Redis authentication failed for user '{cfg.username}'") from e
        except redis.ConnectionError as e:
            raise KctlConnectionError(f"{cfg.host}:{cfg.port}", e) from e
        except Exception as e:
            raise KctlConnectionError(f"{cfg.host}:{cfg.port}", e) from e

    def execute(self, *args: str) -> Any:
        """Execute a single Redis command."""
        if self._redis is None:
            raise RedisCommandError("Not connected. Call connect() first.")
        try:
            return self._redis.execute_command(*args)
        except redis.RedisError as e:
            raise RedisCommandError(str(e), command=" ".join(str(a) for a in args)) from e

    def pipeline(self) -> redis.client.Pipeline:  # type: ignore[type-arg]
        """Get a pipeline for batched commands."""
        if self._redis is None:
            raise RedisCommandError("Not connected. Call connect() first.")
        return self._redis.pipeline()

    @property
    def r(self) -> redis.Redis:  # type: ignore[type-arg]
        """Direct access to redis-py client for native API."""
        if self._redis is None:
            raise RedisCommandError("Not connected. Call connect() first.")
        return self._redis

    def info(self, section: str | None = None) -> dict[str, Any]:
        """Get Redis INFO as a parsed dict."""
        if self._redis is None:
            raise RedisCommandError("Not connected. Call connect() first.")
        if section:
            return self._redis.info(section)
        return self._redis.info()

    @property
    def server_version(self) -> str:
        """Get Redis server version string."""
        info = self.info("server")
        return info.get("redis_version", "unknown")

    def close(self) -> None:
        """Close connection and tunnel."""
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None
        if self._tunnel is not None:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None

    def __enter__(self) -> RedisClient:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
