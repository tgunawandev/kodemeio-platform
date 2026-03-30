"""Checker: error handling patterns."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

MAIN_TSX_CHECKS = ["ErrorBoundary", "Sentry.init", "getErrorMessage"]

BARE_CATCH_PATTERN = re.compile(r"catch\s*\([^)]*\)\s*\{[^}]*(?:console\.log|console\.error)\b")


class ErrorsChecker:
    name = "errors"
    label = "Error Handling"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # main.tsx checks
        main_tsx = src / "main.tsx"
        if main_tsx.is_file():
            content = main_tsx.read_text()
            for check in MAIN_TSX_CHECKS:
                if check not in content:
                    violations.append(
                        Violation(
                            file="src/main.tsx",
                            message=f"Missing {check} in main.tsx",
                            fix_hint=f"Add {check} for proper error handling",
                        )
                    )
        else:
            violations.append(Violation(file="src/main.tsx", message="main.tsx not found"))

        # Scan for bare catch + console.log/error patterns
        for ext in ("*.ts", "*.tsx"):
            for f in src.rglob(ext):
                if "__tests__" in f.parts:
                    continue
                try:
                    text = f.read_text()
                except OSError:
                    continue

                rel = str(f.relative_to(app_path))
                for match in BARE_CATCH_PATTERN.finditer(text):
                    # Find the line number
                    line_num = text[: match.start()].count("\n") + 1
                    violations.append(
                        Violation(
                            file=rel,
                            line=line_num,
                            message="Bare catch with console.log/error — use getErrorMessage + toast",
                            fix_hint="Use getErrorMessage(err) and toast.error() or Sentry.captureException()",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
