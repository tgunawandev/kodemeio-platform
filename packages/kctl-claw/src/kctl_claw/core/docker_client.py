"""Docker compose and exec wrapper for container-side operations."""

from __future__ import annotations

import subprocess
from datetime import UTC
from pathlib import Path

from kctl_claw.core.exceptions import DockerError


class DockerClient:
    """Docker Compose and exec operations for OpenClaw container management."""

    def __init__(
        self,
        compose_file: Path,
        env_file: Path,
        project_name: str = "openclaw",
        service: str = "openclaw-gateway",
    ):
        self._compose_file = compose_file
        self._env_file = env_file
        self._project_name = project_name
        self._default_service = service

    def _compose_cmd(self) -> list[str]:
        """Build the base docker compose command with file and env-file flags."""
        return [
            "docker",
            "compose",
            "-f",
            str(self._compose_file),
            "--env-file",
            str(self._env_file),
        ]

    def _run(
        self,
        cmd: list[str],
        capture: bool = True,
        check: bool = True,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess command, raising DockerError on failure."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise DockerError(command=" ".join(cmd), returncode=-1, stderr="Command timed out") from e

        if check and result.returncode != 0:
            raise DockerError(
                command=" ".join(cmd),
                returncode=result.returncode,
                stderr=result.stderr[:1000] if capture else "",
            )
        return result

    # --- Lifecycle ---

    def up(self, build: bool = False, detach: bool = True) -> None:
        """Start services with docker compose up."""
        cmd = [*self._compose_cmd(), "up"]
        if detach:
            cmd.append("-d")
        if build:
            cmd.append("--build")
        self._run(cmd, capture=False, timeout=600)

    def down(self) -> None:
        """Stop and remove services with docker compose down."""
        self._run([*self._compose_cmd(), "down"])

    def restart(self, service: str | None = None) -> None:
        """Restart a service."""
        svc = service or self._default_service
        self._run([*self._compose_cmd(), "restart", svc])

    def pull(self) -> None:
        """Pull latest images."""
        self._run([*self._compose_cmd(), "pull"])

    # --- Status ---

    def ps(self) -> str:
        """Get service status table."""
        result = self._run([*self._compose_cmd(), "ps", "--format", "table"])
        return result.stdout

    def is_running(self) -> bool:
        """Check if the default service is running."""
        try:
            result = self._run(
                [*self._compose_cmd(), "ps", "--status", "running", "-q"],
                check=False,
            )
            return bool(result.stdout.strip())
        except DockerError:
            return False

    # --- Logs ---

    def logs(self, service: str | None = None, tail: int = 100, follow: bool = False) -> None:
        """Stream or print service logs (prints directly, not captured)."""
        svc = service or self._default_service
        cmd = [*self._compose_cmd(), "logs", "--tail", str(tail), svc]
        if follow:
            cmd.insert(-1, "-f")
        subprocess.run(cmd)

    def logs_grep(self, pattern: str, service: str | None = None, tail: int = 500) -> str:
        """Grep service logs for a pattern."""
        svc = service or self._default_service
        result = self._run([*self._compose_cmd(), "logs", "--tail", str(tail), "--no-color", svc])
        lines = [line for line in result.stdout.splitlines() if pattern.lower() in line.lower()]
        return "\n".join(lines)

    # --- Exec ---

    def exec_cmd(self, command: list[str], service: str | None = None) -> str:
        """Run a command inside a running container, returning stdout."""
        svc = service or self._default_service
        result = self._run([*self._compose_cmd(), "exec", "-T", svc, *command])
        return result.stdout

    def exec_interactive(self, command: list[str], service: str | None = None) -> None:
        """Run an interactive command inside a running container."""
        svc = service or self._default_service
        subprocess.run([*self._compose_cmd(), "exec", svc, *command])

    # --- Volumes ---

    def backup_volumes(self, output_dir: Path, project_name: str | None = None) -> Path:
        """Create timestamped backup of Docker volumes."""
        from datetime import datetime

        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        backup_dir = output_dir / ts
        backup_dir.mkdir(parents=True, exist_ok=True)

        pname = project_name or self._project_name
        for vol_suffix in ["openclaw-data", "openclaw-workspace"]:
            vol_name = f"{pname}_{vol_suffix}"
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vol_name}:/data:ro",
                    "-v",
                    f"{str(backup_dir)}:/backup",
                    "alpine:3",
                    "tar",
                    "czf",
                    f"/backup/{vol_suffix}.tar.gz",
                    "-C",
                    "/data",
                    ".",
                ]
            )
        return backup_dir

    def restore_volumes(self, backup_dir: Path, project_name: str | None = None) -> None:
        """Restore Docker volumes from backup."""
        pname = project_name or self._project_name
        for vol_suffix in ["openclaw-data", "openclaw-workspace"]:
            vol_name = f"{pname}_{vol_suffix}"
            archive = backup_dir / f"{vol_suffix}.tar.gz"
            if not archive.exists():
                continue
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vol_name}:/data",
                    "-v",
                    f"{str(backup_dir)}:/backup:ro",
                    "alpine:3",
                    "sh",
                    "-c",
                    f"rm -rf /data/* && tar xzf /backup/{vol_suffix}.tar.gz -C /data",
                ]
            )
