"""Path resolution — works from anywhere (local, container, CI)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def resolve_paths() -> dict[str, Path | None]:
    """Resolve key directories. Works whether or not inside the repo."""
    claude_dir = Path.home() / ".claude"
    repo_dir = _find_repo()
    return {
        "claude_dir": claude_dir,
        "repo_dir": repo_dir,
        "config_dir": repo_dir / "config" / ".claude" if repo_dir else None,
        "scripts_dir": repo_dir / "scripts" if repo_dir else None,
    }


def _find_repo() -> Path | None:
    """Find the kodemeio-claude repo root."""
    # 1. Check if we're inside the repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            candidate = Path(result.stdout.strip())
            if (candidate / "config" / ".claude").is_dir():
                return candidate
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Check well-known paths
    for path in [
        Path.home() / "project" / "00-new-projects" / "kodemeio-app" / "kodemeio-claude",
        Path("/opt/dev/kodemeio-claude"),
        Path("/opt/dev/kodemeio-app/kodemeio-claude"),
    ]:
        if (path / "config" / ".claude").is_dir():
            return path

    return None
