"""Shell command runner with structured error handling."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from kctl_common.exceptions import CommandError


def run(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = True,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command, raising CommandError on failure."""
    run_env = None
    if env:
        run_env = dict(os.environ)
        run_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            env=run_env,
        )
        if check and result.returncode != 0:
            raise CommandError(" ".join(cmd), result.returncode, result.stderr)
        return result
    except subprocess.TimeoutExpired as e:
        raise CommandError(" ".join(cmd), -1, f"Command timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise CommandError(" ".join(cmd), -1, f"Command not found: {cmd[0]}") from e


def run_quiet(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run a command, returning result without raising on failure."""
    return run(cmd, cwd=cwd, check=False, timeout=timeout)


def get_git_sha(cwd: Path | None = None) -> str:
    """Get current git commit SHA."""
    result = run_quiet(["git", "rev-parse", "HEAD"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def get_git_branch(cwd: Path | None = None) -> str:
    """Get current git branch name."""
    result = run_quiet(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""
