"""Checker: testing setup."""

from __future__ import annotations

import json
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


class TestingChecker:
    name = "testing"
    label = "Testing Setup"
    max_points = 4

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # __tests__/ directory with test files
        tests_dir = src / "__tests__"
        if tests_dir.is_dir():
            test_files = list(tests_dir.rglob("*.test.tsx")) + list(tests_dir.rglob("*.test.ts"))
            if not test_files:
                violations.append(
                    Violation(
                        file="src/__tests__/",
                        message="No test files found in __tests__/",
                        fix_hint="Add .test.tsx/.test.ts files",
                    )
                )
        else:
            violations.append(
                Violation(
                    file="src/__tests__/",
                    message="Missing __tests__/ directory",
                    fix_hint="Create src/__tests__/ with test files",
                )
            )

        # package.json test scripts
        pkg = app_path / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
            scripts = data.get("scripts", {})
            for s in ("test", "test:ci"):
                if s not in scripts:
                    violations.append(
                        Violation(
                            file="package.json",
                            message=f'Missing script: "{s}"',
                            fix_hint=f"Add {s} script to package.json",
                        )
                    )

        # vitest config
        vitest_config = app_path / "vitest.config.ts"
        vite_config = app_path / "vite.config.ts"
        has_vitest_config = vitest_config.is_file()
        if not has_vitest_config and vite_config.is_file():
            content = vite_config.read_text()
            has_vitest_config = (
                ("test" in content and "vitest" in content.lower()) or "test:" in content or "test :" in content
            )

        if not has_vitest_config:
            violations.append(
                Violation(
                    file="vitest.config.ts",
                    message="No vitest configuration found",
                    fix_hint="Add vitest.config.ts or test config in vite.config.ts",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
