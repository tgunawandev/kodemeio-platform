"""Checker: import conventions."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

_SKIP_PARTS = {"node_modules", "generated", "__tests__"}


def _should_skip(file_path: Path) -> bool:
    return bool(_SKIP_PARTS & set(file_path.parts))


class ImportsChecker:
    name = "imports"
    label = "Import Conventions"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"
        if not src.is_dir():
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        for ext in ("*.ts", "*.tsx"):
            for f in src.rglob(ext):
                if _should_skip(f):
                    continue
                rel = str(f.relative_to(app_path))
                try:
                    lines = f.read_text().splitlines()
                except OSError:
                    continue

                for i, line in enumerate(lines, 1):
                    # "use client" directive
                    if re.search(r'"use client"', line) or re.search(r"'use client'", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message='"use client" directive not needed in Vite apps',
                                fix_hint="Remove the directive",
                                auto_fixable=True,
                            )
                        )

                    # Deep relative imports ../../
                    if re.search(r'from\s+["\']\.\.\/\.\.', line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="Deep relative import (../../) — use @/ alias",
                                fix_hint="Replace with @/ path alias",
                                auto_fixable=True,
                            )
                        )

                    # Direct @/generated/ imports outside types/api.ts
                    if re.search(r'from\s+["\']@/generated/', line):
                        if not rel.endswith("types/api.ts"):
                            violations.append(
                                Violation(
                                    file=rel,
                                    line=i,
                                    message="Direct @/generated/ import — use @/types/api instead",
                                    fix_hint="Import from @/types/api",
                                    auto_fixable=True,
                                )
                            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
