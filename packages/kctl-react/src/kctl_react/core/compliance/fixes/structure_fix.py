"""Fixer: create missing required directories."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.checks.structure import REQUIRED_DIRS


def fix_structure(app_path: Path, app_name: str, dry_run: bool = False) -> int:
    """Create missing required directories. Return count of fixes applied."""
    src = app_path / "src"
    count = 0
    for d in REQUIRED_DIRS:
        target = src / d
        if not target.is_dir():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            count += 1
    return count
