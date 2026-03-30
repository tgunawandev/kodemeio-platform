"""Checker: project file/directory structure."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

REQUIRED_DIRS = [
    "api",
    "pages",
    "components",
    "config",
    "hooks",
    "contexts",
    "constants",
    "types",
    "i18n",
    "utils",
    "__tests__",
]

REQUIRED_FILES = [
    "main.tsx",
    "App.tsx",
    "config/navConfig.tsx",
    "components/AppLayout.tsx",
    "api/client.ts",
    "types/api.ts",
]


class StructureChecker:
    name = "structure"
    label = "File Structure"
    max_points = 8

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        for d in REQUIRED_DIRS:
            if not (src / d).is_dir():
                violations.append(
                    Violation(
                        file=f"src/{d}/",
                        message=f"Missing required directory: src/{d}/",
                        fix_hint=f"mkdir -p apps/{app_name}/src/{d}",
                    )
                )

        for f in REQUIRED_FILES:
            if not (src / f).is_file():
                violations.append(
                    Violation(
                        file=f"src/{f}",
                        message=f"Missing required file: src/{f}",
                    )
                )

        # .env.example in app root
        if not (app_path / ".env.example").is_file():
            violations.append(
                Violation(
                    file=".env.example",
                    message="Missing .env.example in app root",
                    fix_hint="Create .env.example with sanitized env vars",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
