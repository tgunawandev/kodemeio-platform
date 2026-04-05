"""SSH tunnel management for database CLIs.

Provides SSHTunnel context manager that wraps sshtunnel.SSHTunnelForwarder
with standardized error handling and configuration.

Usage:
    from kctl_lib.ssh_tunnel import SSHTunnel

    with SSHTunnel(ssh_host="91.98.80.207", remote_port=5432) as tunnel:
        conn = psycopg.connect(host="127.0.0.1", port=tunnel.local_port)
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SSHTunnel:
    """SSH tunnel context manager for database access.

    Wraps sshtunnel.SSHTunnelForwarder with consistent config and error handling.
    """

    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key: str | None = None
    remote_host: str = "127.0.0.1"
    remote_port: int = 5432
    local_host: str = "127.0.0.1"

    _tunnel: Any = field(default=None, init=False, repr=False)

    @property
    def local_port(self) -> int:
        """Get the local port for the tunnel (available after start)."""
        if self._tunnel is None:
            raise RuntimeError("Tunnel not started")
        return int(self._tunnel.local_bind_port)

    def start(self) -> int:
        """Start the SSH tunnel. Returns the local port."""
        from sshtunnel import SSHTunnelForwarder

        ssh_key_path = str(Path(self.ssh_key).expanduser()) if self.ssh_key else None

        try:
            self._tunnel = SSHTunnelForwarder(
                (self.ssh_host, self.ssh_port),
                ssh_username=self.ssh_user,
                ssh_pkey=ssh_key_path,
                remote_bind_address=(self.remote_host, self.remote_port),
                local_bind_address=(self.local_host,),
            )
            self._tunnel.start()
        except Exception as e:
            from kctl_lib.exceptions import ConnectionError as KctlConnectionError

            raise KctlConnectionError(
                f"{self.ssh_user}@{self.ssh_host}:{self.ssh_port}",
                e,
            ) from e

        return self.local_port

    def stop(self) -> None:
        """Stop the SSH tunnel."""
        if self._tunnel is not None:
            with contextlib.suppress(Exception):
                self._tunnel.stop()
            self._tunnel = None

    def __enter__(self) -> SSHTunnel:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
