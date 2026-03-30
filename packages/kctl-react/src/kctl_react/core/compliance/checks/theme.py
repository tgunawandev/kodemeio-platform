"""Checker: theme setup and color token isolation."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

COLOR_TOKEN_PATTERN = re.compile(r"--(?:primary|secondary|accent|destructive)\s*:")


class ThemeChecker:
    name = "theme"
    label = "Theme Setup"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # index.css should import themes/{app}.css
        index_css = src / "index.css"
        if index_css.is_file():
            content = index_css.read_text()
            expected_import = f"themes/{app_name}.css"
            if expected_import not in content:
                violations.append(
                    Violation(
                        file="src/index.css",
                        message=f"index.css does not import {expected_import}",
                        fix_hint=f'Add @import "{expected_import}" to index.css',
                    )
                )

            # No color tokens in index.css
            for i, line in enumerate(content.splitlines(), 1):
                if COLOR_TOKEN_PATTERN.search(line):
                    violations.append(
                        Violation(
                            file="src/index.css",
                            line=i,
                            message="Color token in index.css — should be in theme file",
                            fix_hint="Move color tokens to themes/{app}.css",
                        )
                    )
        else:
            violations.append(Violation(file="src/index.css", message="Missing index.css"))

        # Check globals.css for color tokens too
        globals_css = src / "globals.css"
        if globals_css.is_file():
            content = globals_css.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if COLOR_TOKEN_PATTERN.search(line):
                    violations.append(
                        Violation(
                            file="src/globals.css",
                            line=i,
                            message="Color token in globals.css — should be in theme file",
                            fix_hint="Move color tokens to themes/{app}.css",
                        )
                    )

        # ThemeToggle in AppLayout.tsx
        layout = src / "components" / "AppLayout.tsx"
        if layout.is_file():
            content = layout.read_text()
            if "ThemeToggle" not in content:
                violations.append(
                    Violation(
                        file="src/components/AppLayout.tsx",
                        message="Missing ThemeToggle in AppLayout",
                        fix_hint="Add ThemeToggle from @kodemeio/ui",
                    )
                )
            # Check app-specific storageKey
            if "storageKey" not in content and "ThemeToggle" in content:
                violations.append(
                    Violation(
                        file="src/components/AppLayout.tsx",
                        message="ThemeToggle missing app-specific storageKey",
                        fix_hint=f'Add storageKey="{app_name}_theme"',
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
