"""Checker: package.json scripts."""

from __future__ import annotations

import json
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

REQUIRED_SCRIPTS = [
    "dev",
    "build",
    "preview",
    "lint",
    "type-check",
    "test",
    "fetch:schema",
    "generate:api",
]

HOOK_SCRIPTS = ["predev", "prebuild"]


class ScriptsChecker:
    name = "scripts"
    label = "Package Scripts"
    max_points = 4

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []

        pkg = app_path / "package.json"
        if not pkg.is_file():
            violations.append(Violation(file="package.json", message="Missing package.json"))
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        try:
            data = json.loads(pkg.read_text())
        except (json.JSONDecodeError, OSError):
            violations.append(
                Violation(
                    file="package.json",
                    message="Failed to parse package.json",
                )
            )
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        scripts = data.get("scripts", {})

        for script in REQUIRED_SCRIPTS:
            if script not in scripts:
                violations.append(
                    Violation(
                        file="package.json",
                        message=f'Missing required script: "{script}"',
                        fix_hint=f"Add {script} script to package.json",
                    )
                )

        for hook in HOOK_SCRIPTS:
            if hook not in scripts:
                violations.append(
                    Violation(
                        file="package.json",
                        message=f'Missing hook script: "{hook}"',
                        fix_hint=f"Add {hook} hook to package.json",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
