"""Fixer: remove 'use client' directives from .ts/.tsx files."""

from __future__ import annotations

import re
from pathlib import Path

_USE_CLIENT_RE = re.compile(r'^["\']use client["\']\s*;?\s*\n', re.MULTILINE)

_SKIP_DIRS = {"node_modules", "generated", ".git", "dist", "__pycache__"}


def fix_imports(app_path: Path, app_name: str, dry_run: bool = False) -> int:
    """Remove 'use client' directives. Return count of fixes applied."""
    src = app_path / "src"
    if not src.is_dir():
        return 0

    count = 0
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".ts", ".tsx"):
            continue
        # Skip excluded directories
        if any(part in _SKIP_DIRS for part in f.relative_to(src).parts):
            continue

        text = f.read_text(encoding="utf-8")
        new_text = _USE_CLIENT_RE.sub("", text)
        if new_text != text:
            if not dry_run:
                f.write_text(new_text, encoding="utf-8")
            count += 1

    return count
