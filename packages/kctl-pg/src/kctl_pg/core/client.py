"""PostgreSQL client with SSH tunnel support using psycopg3.

Connects to remote PostgreSQL servers through an SSH tunnel
using sshtunnel + psycopg3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sshtunnel import SSHTunnelForwarder

from kctl_pg.core.config import ServiceConfig
from kctl_pg.core.exceptions import (
    AuthenticationError,
    DatabaseError,
    KctlConnectionError,
    SSHTunnelError,
)


class PostgresClient:
    """PostgreSQL client that connects through an SSH tunnel."""

    def __init__(self, config: ServiceConfig, database: str = "postgres"):
        if not config.host:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No PostgreSQL host configured. Run: kctl-pg config init"),
            )
        if not config.ssh_host:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No SSH host configured. Run: kctl-pg config init"),
            )

        self._config = config
        self._database = database
        self._tunnel: SSHTunnelForwarder | None = None
        self._conn: psycopg.Connection | None = None

    def connect(self) -> None:
        """Open SSH tunnel and connect to PostgreSQL."""
        cfg = self._config

        # Resolve SSH key path
        ssh_key = str(Path(cfg.ssh_key).expanduser()) if cfg.ssh_key else None

        try:
            self._tunnel = SSHTunnelForwarder(
                (cfg.ssh_host, cfg.ssh_port),
                ssh_username=cfg.ssh_user,
                ssh_pkey=ssh_key,
                remote_bind_address=(cfg.host, cfg.port),
                local_bind_address=("127.0.0.1",),
            )
            self._tunnel.start()
        except Exception as e:
            raise SSHTunnelError(cfg.ssh_host, e) from e

        local_port = self._tunnel.local_bind_port

        try:
            self._conn = psycopg.connect(
                host="127.0.0.1",
                port=local_port,
                user=cfg.user,
                password=cfg.password,
                dbname=self._database,
                row_factory=dict_row,
                autocommit=True,
            )
        except psycopg.OperationalError as e:
            err_msg = str(e)
            if "authentication failed" in err_msg or "password" in err_msg:
                raise AuthenticationError(f"Database authentication failed for user '{cfg.user}'") from e
            raise KctlConnectionError(f"{cfg.host}:{cfg.port}", e) from e
        except Exception as e:
            raise KctlConnectionError(f"{cfg.host}:{cfg.port}", e) from e

    def execute(self, sql: str | Any, params: tuple | dict | None = None) -> None:
        """Execute SQL without returning results."""
        assert self._conn is not None, "Not connected. Call connect() first."
        try:
            self._conn.execute(sql, params)
        except psycopg.Error as e:
            raise DatabaseError(str(e), query=sql) from e

    def fetchall(self, sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
        """Execute SQL and return all rows as dicts."""
        assert self._conn is not None, "Not connected. Call connect() first."
        try:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()
        except psycopg.Error as e:
            raise DatabaseError(str(e), query=sql) from e

    def fetchone(self, sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
        """Execute SQL and return one row as dict, or None."""
        assert self._conn is not None, "Not connected. Call connect() first."
        try:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()
        except psycopg.Error as e:
            raise DatabaseError(str(e), query=sql) from e

    def fetchval(self, sql: str, params: tuple | dict | None = None) -> Any:
        """Execute SQL and return a single scalar value."""
        assert self._conn is not None, "Not connected. Call connect() first."
        try:
            cur = self._conn.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                return None
            # dict_row returns dict, get first value
            return next(iter(row.values()))
        except psycopg.Error as e:
            raise DatabaseError(str(e), query=sql) from e

    @property
    def server_version(self) -> str:
        """Get PostgreSQL server version string."""
        row = self.fetchone("SELECT version()")
        return row["version"] if row else "unknown"

    @property
    def short_version(self) -> str:
        """Get short version like '16.3'."""
        row = self.fetchone("SHOW server_version")
        return row["server_version"] if row else "unknown"

    def close(self) -> None:
        """Close connection and tunnel."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        if self._tunnel is not None:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None

    def __enter__(self) -> PostgresClient:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
