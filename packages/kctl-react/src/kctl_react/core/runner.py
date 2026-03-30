"""Shell command runner — delegates to kctl-common, adds pnpm/turbo helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kctl_common.runner import get_git_branch, get_git_sha, run, run_quiet

__all__ = ["get_git_branch", "get_git_sha", "run", "run_quiet", "run_pnpm", "run_turbo"]


def run_pnpm(
    args: list[str],
    cwd: Path,
    capture: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run pnpm command in the monorepo."""
    return run(["pnpm", *args], cwd=cwd, capture=capture, timeout=timeout)


def run_turbo(
    task: str,
    cwd: Path,
    filter_app: str | None = None,
    capture: bool = True,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Run turbo task with optional app filter."""
    cmd = ["pnpm", "turbo", "run", task]
    if filter_app:
        cmd.extend(["--filter", f"@kodemeio/{filter_app}"])
    return run(cmd, cwd=cwd, capture=capture, timeout=timeout)
