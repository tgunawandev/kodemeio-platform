"""SSH + docker compose mmctl transport."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any

from kctl_lib.exceptions import CommandError
from kctl_lib.ssh import SSHResult, ssh_run


@dataclass
class MMExec:
    ssh_host: str
    ssh_user: str
    compose_path: str
    compose_service: str = "mattermost"
    compose_project: str | None = None  # override docker compose project name (Dokploy sets custom names)

    def _compose_prefix(self) -> str:
        parts = ["docker", "compose"]
        if self.compose_project:
            parts += ["-p", shlex.quote(self.compose_project)]
        parts += ["-f", shlex.quote(self.compose_path)]
        return " ".join(parts)

    def _build(self, args: list[str], json_out: bool) -> str:
        mmctl_args = ["mmctl", "--local"]
        if json_out:
            mmctl_args += ["--format", "json"]
        mmctl_args += args
        inner = " ".join(shlex.quote(a) for a in mmctl_args)
        return f"{self._compose_prefix()} exec -T {shlex.quote(self.compose_service)} {inner}"

    def mmctl(self, args: list[str]) -> SSHResult:
        cmd = self._build(args, json_out=False)
        result = ssh_run(host=self.ssh_host, user=self.ssh_user, command=cmd)
        if result.returncode != 0:
            raise CommandError(cmd, result.returncode, result.stderr.strip())
        return result

    def mmctl_json(self, args: list[str]) -> Any:
        cmd = self._build(args, json_out=True)
        result = ssh_run(host=self.ssh_host, user=self.ssh_user, command=cmd)
        if result.returncode != 0:
            raise CommandError(cmd, result.returncode, result.stderr.strip())
        return json.loads(result.stdout)

    def docker_compose(self, args: list[str]) -> SSHResult:
        inner = " ".join(shlex.quote(a) for a in args)
        cmd = f"{self._compose_prefix()} {inner}"
        result = ssh_run(host=self.ssh_host, user=self.ssh_user, command=cmd)
        if result.returncode != 0:
            raise CommandError(cmd, result.returncode, result.stderr.strip())
        return result
