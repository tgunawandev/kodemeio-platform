"""Checker: OpenAPI codegen setup."""

from __future__ import annotations

import json
import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


class CodegenChecker:
    name = "codegen"
    label = "OpenAPI Codegen"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []

        # openapi-ts.config.ts must exist
        if not (app_path / "openapi-ts.config.ts").is_file():
            violations.append(
                Violation(
                    file="openapi-ts.config.ts",
                    message="Missing openapi-ts.config.ts",
                    fix_hint="Create OpenAPI codegen config",
                    auto_fixable=True,
                )
            )

        # types/api.ts must reference @/generated/types.gen
        api_ts = app_path / "src" / "types" / "api.ts"
        if api_ts.is_file():
            content = api_ts.read_text()
            if "@/generated/types.gen" not in content:
                violations.append(
                    Violation(
                        file="src/types/api.ts",
                        message="types/api.ts does not re-export from @/generated/types.gen",
                        fix_hint="Add export from @/generated/types.gen",
                    )
                )
        else:
            violations.append(
                Violation(
                    file="src/types/api.ts",
                    message="Missing src/types/api.ts",
                )
            )

        # Check for manual API type files in types/
        types_dir = app_path / "src" / "types"
        if types_dir.is_dir():
            manual_pattern = re.compile(r"export\s+(interface|type)\s+\w+(Response|Request|Item|Data)\b")
            for ts_file in types_dir.glob("*.ts"):
                if ts_file.name == "api.ts":
                    continue
                try:
                    text = ts_file.read_text()
                except OSError:
                    continue
                if manual_pattern.search(text):
                    violations.append(
                        Violation(
                            file=f"src/types/{ts_file.name}",
                            message=f"Manual API type definitions in {ts_file.name} — use OpenAPI codegen",
                            fix_hint="Move types to OpenAPI schema and regenerate",
                        )
                    )

        # package.json scripts
        pkg = app_path / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
            scripts = data.get("scripts", {})
            for script_name in ("fetch:schema", "generate:api"):
                if script_name not in scripts:
                    violations.append(
                        Violation(
                            file="package.json",
                            message=f'Missing script: "{script_name}"',
                            fix_hint=f"Add {script_name} script to package.json",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
