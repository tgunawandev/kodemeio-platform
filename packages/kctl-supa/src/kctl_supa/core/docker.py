"""DockerOps — SSH + docker operations for a remote Supabase host.

Uses paramiko for SSH connections and runs docker/docker compose commands
on the remote host via exec_command.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any

import paramiko

from kctl_supa.core.exceptions import DockerError

if TYPE_CHECKING:
    from kctl_supa.core.config import ServiceConfig


class DockerOps:
    """Remote docker operations over SSH for a Supabase host."""

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._ssh_client: paramiko.SSHClient | None = None

    # ------------------------------------------------------------------
    # SSH connection (lazy)
    # ------------------------------------------------------------------

    @property
    def ssh(self) -> paramiko.SSHClient:
        """Return a connected paramiko SSHClient, creating it if needed."""
        if self._ssh_client is None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            key_path = str(Path(self._config.ssh_key).expanduser())

            try:
                client.connect(
                    hostname=self._config.ssh_host,
                    port=self._config.ssh_port,
                    username=self._config.ssh_user,
                    key_filename=key_path,
                    timeout=10,
                )
            except (paramiko.SSHException, OSError) as exc:
                raise DockerError(f"SSH connection failed to {self._config.ssh_host}: {exc}") from exc

            self._ssh_client = client
        return self._ssh_client

    # ------------------------------------------------------------------
    # Core exec
    # ------------------------------------------------------------------

    def exec(self, command: str, timeout: int = 60) -> str:
        """Run a command on the remote host via SSH.

        Returns stdout as a string.
        Raises DockerError on non-zero exit.
        """
        try:
            _stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        except (paramiko.SSHException, OSError) as exc:
            raise DockerError(f"SSH exec failed: {exc}") from exc

        if exit_code != 0:
            raise DockerError(f"Command exited {exit_code}: {command}\nstderr: {err}")
        return out

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    def resolve_container(self, service: str) -> str:
        """Resolve the full container name for a service.

        Tries {prefix}-{service}-1 first (Docker Compose v2 default),
        falls back to {prefix}-{service} for explicit container_name setups.
        Returns the first name that exists.
        """
        prefix = self._config.container_prefix
        if not prefix:
            return service

        name_v2 = f"{prefix}-{service}-1"
        try:
            self.exec(f"docker inspect --format '{{{{.Name}}}}' {name_v2}")
            return name_v2
        except DockerError:
            return f"{prefix}-{service}"

    def docker_exec(self, container: str, command: str) -> str:
        """Run a command inside a named container.

        Tries {prefix}-{container}-1 first (Docker Compose default),
        falls back to {prefix}-{container} for explicit container_name setups.
        """
        name = self.resolve_container(container)
        return self.exec(f"docker exec {name} {command}")

    def psql(self, query: str, database: str = "postgres") -> str:
        """Run a psql query inside the Supabase db container."""
        quoted = shlex.quote(query)
        return self.docker_exec("db", f"psql -U postgres -d {database} -c {quoted}")

    def psql_stdin(self, sql: str, database: str = "postgres", timeout: int = 300) -> str:
        """Run SQL inside the Supabase db container by piping via stdin.

        This avoids shell argument length limits for large SQL files.
        """
        container = self.resolve_container("db")
        cmd = f"docker exec -i {container} psql -U postgres -d {database}"
        try:
            transport = self.ssh.get_transport()
            if transport is None:
                raise DockerError("SSH transport is None")
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.exec_command(cmd)
            channel.sendall(sql.encode("utf-8"))
            channel.shutdown_write()

            stdout_chunks: list[bytes] = []
            stderr_chunks: list[bytes] = []
            while True:
                if channel.recv_ready():
                    stdout_chunks.append(channel.recv(65536))
                if channel.recv_stderr_ready():
                    stderr_chunks.append(channel.recv_stderr(65536))
                if channel.exit_status_ready():
                    # Drain remaining data
                    while channel.recv_ready():
                        stdout_chunks.append(channel.recv(65536))
                    while channel.recv_stderr_ready():
                        stderr_chunks.append(channel.recv_stderr(65536))
                    break

            exit_code = channel.recv_exit_status()
            out = b"".join(stdout_chunks).decode("utf-8", errors="replace").strip()
            err = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
            channel.close()
        except (paramiko.SSHException, OSError) as exc:
            raise DockerError(f"SSH exec failed: {exc}") from exc

        if exit_code != 0:
            raise DockerError(f"psql exited {exit_code}\nstderr: {err}")
        return out

    # ------------------------------------------------------------------
    # Container inspection
    # ------------------------------------------------------------------

    def container_status(self) -> list[dict[str, Any]]:
        """Return a list of container dicts matching the container prefix.

        Each dict contains the raw fields from `docker ps --format json`.
        """
        prefix = self._config.container_prefix
        filter_flag = f"--filter name={prefix}" if prefix else ""
        cmd = f"docker ps {filter_flag} --format json"

        try:
            output = self.exec(cmd)
        except DockerError:
            return []

        containers: list[dict[str, Any]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return containers

    # ------------------------------------------------------------------
    # Compose operations
    # ------------------------------------------------------------------

    def _compose_cmd(self, service: str, action: str, compose_file: str = "") -> str:
        """Build a docker compose command string."""
        file_flag = f"-f {compose_file}" if compose_file else ""
        return f"docker compose {file_flag} {action} {service}".strip()

    def compose_up(self, service: str = "", compose_file: str = "") -> str:
        """docker compose up -d [service]"""
        return self.exec(self._compose_cmd(service, "up -d", compose_file))

    def compose_down(self, service: str = "", compose_file: str = "") -> str:
        """docker compose down [service]"""
        return self.exec(self._compose_cmd(service, "down", compose_file))

    def compose_restart(self, service: str = "", compose_file: str = "") -> str:
        """docker compose restart [service]"""
        return self.exec(self._compose_cmd(service, "restart", compose_file))

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def logs(self, service: str, tail: int = 100) -> str:
        """Fetch the last N lines of logs for a container."""
        name = self.resolve_container(service)
        return self.exec(f"docker logs --tail {tail} {name}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SSH connection if open."""
        if self._ssh_client is not None:
            try:
                self._ssh_client.close()
            except Exception:  # noqa: BLE001
                pass
            self._ssh_client = None

    def __enter__(self) -> DockerOps:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
