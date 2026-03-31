"""RustDesk server executor — runs commands locally or via SSH."""

from __future__ import annotations

import csv
import json
import shlex
from io import StringIO

from kctl_lib.exceptions import CommandError, DockerError
from kctl_lib.runner import run, run_quiet

from kctl_rustdesk.core.config import ServiceConfig


class RustDeskExecutor:
    """Execute commands on RustDesk server (local or remote via SSH)."""

    DB_PATH = "/root/db_v2.sqlite3"
    KEY_PUB_PATH = "/root/id_ed25519.pub"
    KEY_PRIV_PATH = "/root/id_ed25519"

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.is_remote = config.host not in ("localhost", "127.0.0.1", "")
        self.hbbs_container = f"{config.project_name}-hbbs-1"
        self.hbbr_container = f"{config.project_name}-hbbr-1"

    def _wrap_ssh(self, cmd: list[str]) -> list[str]:
        """Wrap a command in SSH if targeting a remote host."""
        if not self.is_remote:
            return cmd
        remote_cmd = shlex.join(cmd)
        return [
            "ssh", "-o", "StrictHostKeyChecking=accept-new",
            f"{self.config.ssh_user}@{self.config.host}",
            remote_cmd,
        ]

    def shell(self, cmd: list[str], check: bool = True, timeout: int = 30) -> str:
        """Run a shell command on the server."""
        wrapped = self._wrap_ssh(cmd)
        if check:
            result = run(wrapped, timeout=timeout)
        else:
            result = run_quiet(wrapped, timeout=timeout)
        return result.stdout.strip()

    def _dc_cmd(self) -> list[str]:
        """Base docker compose command."""
        return [
            "docker", "compose",
            "-f", self.config.compose_file,
            "-p", self.config.project_name,
        ]

    def docker_exec(self, container: str, cmd: list[str], check: bool = True) -> str:
        """Execute a command inside a container."""
        full_cmd = [*self._dc_cmd(), "exec", "-T", container, *cmd]
        return self.shell(full_cmd, check=check)

    def exec_hbbs(self, cmd: list[str], check: bool = True) -> str:
        """Execute a command in the hbbs container."""
        return self.docker_exec("hbbs", cmd, check=check)

    def exec_hbbr(self, cmd: list[str], check: bool = True) -> str:
        """Execute a command in the hbbr container."""
        return self.docker_exec("hbbr", cmd, check=check)

    def container_running(self, service: str) -> bool:
        """Check if a compose service container is running."""
        try:
            output = self.shell(
                [*self._dc_cmd(), "ps", "--status", "running", "--format", "{{.Service}}"],
                check=False,
            )
            return service in output.splitlines()
        except (CommandError, DockerError):
            return False

    def docker_ps(self) -> list[dict[str, str]]:
        """Get container status as list of dicts."""
        try:
            output = self.shell([*self._dc_cmd(), "ps", "--format", "json"], check=False)
            if not output:
                return []
            containers: list[dict[str, str]] = []
            for line in output.splitlines():
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return containers
        except (CommandError, DockerError):
            return []

    def docker_logs(self, service: str | None = None, tail: int = 100) -> str:
        """Get container logs."""
        cmd = [*self._dc_cmd(), "logs", "--tail", str(tail), "--no-color"]
        if service:
            cmd.append(service)
        return self.shell(cmd, check=False)

    def query_db(self, sql: str) -> list[dict[str, str]]:
        """Run a SQLite query on hbbs and return rows as list of dicts."""
        output = self.exec_hbbs(
            ["sqlite3", "-header", "-csv", self.DB_PATH, sql],
        )
        if not output.strip():
            return []
        reader = csv.DictReader(StringIO(output))
        return [dict(row) for row in reader]

    def query_db_scalar(self, sql: str) -> str:
        """Run a SQLite query that returns a single value."""
        output = self.exec_hbbs(["sqlite3", self.DB_PATH, sql])
        return output.strip()

    def read_file(self, container: str, path: str) -> str:
        """Read a file from inside a container."""
        return self.docker_exec(container, ["cat", path])

    def file_exists(self, container: str, path: str) -> bool:
        """Check if a file exists in a container."""
        try:
            self.docker_exec(container, ["test", "-f", path])
            return True
        except CommandError:
            return False

    def get_public_key(self) -> str:
        """Get the server's public key."""
        return self.exec_hbbs(["cat", self.KEY_PUB_PATH])

    def get_compose_version(self) -> str:
        """Get docker compose version."""
        return self.shell(["docker", "compose", "version", "--short"], check=False)

    def get_container_stats(self, service: str) -> dict[str, str]:
        """Get CPU/memory stats for a container."""
        output = self.shell(
            ["docker", "stats", "--no-stream", "--format",
             "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
             f"{self.config.project_name}-{service}-1"],
            check=False,
        )
        parts = output.split("\t") if output else []
        return {
            "cpu": parts[0] if len(parts) > 0 else "-",
            "mem_usage": parts[1] if len(parts) > 1 else "-",
            "mem_pct": parts[2] if len(parts) > 2 else "-",
        }
