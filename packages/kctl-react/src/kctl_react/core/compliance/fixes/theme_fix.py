"""Fixer: correct theme import path in index.css."""

from __future__ import annotations

import re
from pathlib import Path

_THEME_IMPORT_RE = re.compile(r'@import\s+["\']@kodemeio/tailwind-config/themes/\w+\.css["\']')


def fix_theme(app_path: Path, app_name: str, dry_run: bool = False) -> int:
    """Fix theme import path in index.css. Return count of fixes applied."""
    index_css = app_path / "src" / "index.css"
    if not index_css.is_file():
        return 0

    text = index_css.read_text(encoding="utf-8")
    correct_import = f'@import "@kodemeio/tailwind-config/themes/{app_name}.css"'

    if correct_import in text:
        return 0

    new_text = _THEME_IMPORT_RE.sub(correct_import, text)
    if new_text != text:
        if not dry_run:
            index_css.write_text(new_text, encoding="utf-8")
        return 1

    return 0
