"""Auto-fixers registry."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.fixes.codegen_fix import fix_codegen
from kctl_react.core.compliance.fixes.i18n_fix import fix_i18n
from kctl_react.core.compliance.fixes.imports_fix import fix_imports
from kctl_react.core.compliance.fixes.structure_fix import fix_structure
from kctl_react.core.compliance.fixes.theme_fix import fix_theme

ALL_FIXERS: dict = {
    "structure": fix_structure,
    "imports": fix_imports,
    "i18n": fix_i18n,
    "codegen": fix_codegen,
    "theme": fix_theme,
}


def apply_fixes(
    app_path: Path,
    app_name: str,
    dry_run: bool = False,
    categories: list[str] | None = None,
) -> int:
    """Apply auto-fixes and return count of fixes applied."""
    fixers = {k: v for k, v in ALL_FIXERS.items() if not categories or k in categories}
    total = 0
    for fix_fn in fixers.values():
        total += fix_fn(app_path, app_name, dry_run=dry_run)
    return total
