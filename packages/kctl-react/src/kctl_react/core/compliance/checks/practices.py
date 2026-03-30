"""Checker: coding best practices."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

_SKIP_PARTS = {"node_modules", "__tests__", "generated"}


def _should_skip(file_path: Path) -> bool:
    return bool(_SKIP_PARTS & set(file_path.parts))


class PracticesChecker:
    name = "practices"
    label = "Best Practices"
    max_points = 4

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
                try:
                    lines = f.read_text().splitlines()
                except OSError:
                    continue
                rel = str(f.relative_to(app_path))

                is_user_code = "pages" in f.parts or "components" in f.parts
                for i, line in enumerate(lines, 1):
                    stripped = line.lstrip()
                    if stripped.startswith("//") or stripped.startswith("*"):
                        continue

                    # console.log in production code (pages/components only)
                    if is_user_code and re.search(r"\bconsole\.log\s*\(", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="console.log() in production code",
                                fix_hint="Remove or replace with Sentry.captureMessage",
                            )
                        )

                    # : any type annotation (pages/components only)
                    if is_user_code and re.search(r":\s*any\b", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message=": any type annotation — use proper types",
                                fix_hint="Replace with specific type",
                            )
                        )

                    # process.env instead of import.meta.env (Vite apps)
                    if re.search(r"\bprocess\.env\b", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="process.env — use import.meta.env in Vite apps",
                                fix_hint="Replace process.env.X with import.meta.env.VITE_X",
                                auto_fixable=False,
                            )
                        )

                    # Hardcoded localhost URLs in non-config files
                    if is_user_code and re.search(r"https?://localhost[:\d/]", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="Hardcoded localhost URL — use env variable",
                                fix_hint="Use import.meta.env.VITE_API_BASE_URL",
                            )
                        )

                    # Whole library imports (lodash, date-fns, etc.)
                    if re.search(r'import\s+\w+\s+from\s+["\'](?:lodash|moment|date-fns)["\']', line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="Whole library import — use named imports for tree-shaking",
                                fix_hint='Use import { fn } from "library" instead',
                            )
                        )

                # export default check for page files
                if "pages" in f.parts:
                    text = "\n".join(lines)
                    if re.search(r"\bexport\s+default\b", text):
                        violations.append(
                            Violation(
                                file=rel,
                                message="export default in page — use named export",
                                fix_hint="Use named export instead of export default",
                            )
                        )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
