"""CLI self-update utilities."""

from __future__ import annotations

from kctl_common.runner import run, run_quiet


def check_update(package_name: str, current_version: str) -> str | None:
    result = run_quiet(["pip", "index", "versions", package_name])
    if result.returncode != 0:
        return None
    latest = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("("):
            latest = line.split("(")[0].strip().split()[-1] if line else ""
            break
    if not latest or latest == current_version:
        return None
    try:
        current_parts = [int(x) for x in current_version.split(".")]
        latest_parts = [int(x) for x in latest.split(".")]
        if latest_parts > current_parts:
            return latest
    except ValueError:
        pass
    return None


def update(package_name: str) -> None:
    run(["uv", "tool", "upgrade", package_name])
