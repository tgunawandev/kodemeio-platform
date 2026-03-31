"""Docker Compose management for kctl-* CLI tools."""

from __future__ import annotations

import json
from pathlib import Path

from kctl_lib.runner import run, run_quiet


class DockerManager:
    def __init__(self, compose_file: Path, project_name: str) -> None:
        self.compose_file = compose_file
        self.project_name = project_name

    def _base_cmd(self) -> list[str]:
        return ["docker", "compose", "-f", str(self.compose_file), "-p", self.project_name]

    def up(self, services: list[str] | None = None, detach: bool = True) -> None:
        cmd = [*self._base_cmd(), "up"]
        if detach:
            cmd.append("-d")
        if services:
            cmd.extend(services)
        run(cmd, cwd=self.compose_file.parent)

    def down(self, volumes: bool = False) -> None:
        cmd = [*self._base_cmd(), "down"]
        if volumes:
            cmd.append("-v")
        run(cmd, cwd=self.compose_file.parent)

    def ps(self) -> list[dict]:  # type: ignore[type-arg]
        cmd = [*self._base_cmd(), "ps", "--format", "json"]
        result = run_quiet(cmd, cwd=self.compose_file.parent)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        containers: list[dict] = []  # type: ignore[type-arg]
        for line in result.stdout.strip().splitlines():
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return containers

    def logs(self, service: str | None = None, follow: bool = False, tail: int = 100) -> None:
        cmd = [*self._base_cmd(), "logs", "--tail", str(tail)]
        if follow:
            cmd.append("-f")
        if service:
            cmd.append(service)
        run(cmd, cwd=self.compose_file.parent, capture=False)

    def restart(self, service: str | None = None) -> None:
        cmd = [*self._base_cmd(), "restart"]
        if service:
            cmd.append(service)
        run(cmd, cwd=self.compose_file.parent)

    def image_size(self) -> list[dict]:  # type: ignore[type-arg]
        cmd = [*self._base_cmd(), "images", "--format", "json"]
        result = run_quiet(cmd, cwd=self.compose_file.parent)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        images: list[dict] = []  # type: ignore[type-arg]
        for line in result.stdout.strip().splitlines():
            try:
                images.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return images

    def prune(self, force: bool = False) -> None:
        cmd = ["docker", "system", "prune"]
        if force:
            cmd.append("-f")
        run(cmd, cwd=self.compose_file.parent)

    def exec(self, service: str, command: list[str]) -> str:
        cmd = [*self._base_cmd(), "exec", "-T", service, *command]
        result = run(cmd, cwd=self.compose_file.parent)
        return result.stdout
