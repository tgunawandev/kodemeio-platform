"""Checker: API client patterns."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


class ApiChecker:
    name = "api"
    label = "API Client"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # client.ts must import from @kodemeio/core
        client_ts = src / "api" / "client.ts"
        if client_ts.is_file():
            content = client_ts.read_text()
            if "@kodemeio/core" not in content:
                violations.append(
                    Violation(
                        file="src/api/client.ts",
                        message="client.ts does not import from @kodemeio/core",
                        fix_hint="Use ApiClient from @kodemeio/core",
                    )
                )
        else:
            violations.append(
                Violation(
                    file="src/api/client.ts",
                    message="Missing api/client.ts",
                )
            )

        # No raw fetch() or axios in pages/components
        for subdir in ("pages", "components"):
            scan_dir = src / subdir
            if not scan_dir.is_dir():
                continue
            for tsx_file in scan_dir.rglob("*.tsx"):
                if "__tests__" in tsx_file.parts:
                    continue
                try:
                    lines = tsx_file.read_text().splitlines()
                except OSError:
                    continue
                rel = str(tsx_file.relative_to(app_path))
                for i, line in enumerate(lines, 1):
                    if re.search(r"\bfetch\s*\(", line) and "import" not in line:
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="Raw fetch() call — use ApiClient via hooks",
                                fix_hint="Move API call to a hook using apiClient",
                            )
                        )
                    if re.search(r"\baxios\b", line):
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message="axios usage — use ApiClient from @kodemeio/core",
                                fix_hint="Replace axios with apiClient",
                            )
                        )

        # Hook files should use useQuery/useMutation
        # Skip utility hooks that wrap non-fetch functionality
        _SKIP_HOOKS = {"useExport", "useBarcode", "useSettings", "useWebSocket", "useEventSource"}
        api_dir = src / "api"
        if api_dir.is_dir():
            for hook_file in api_dir.glob("use*.ts"):
                hook_name = hook_file.stem
                if hook_name in _SKIP_HOOKS:
                    continue
                try:
                    content = hook_file.read_text()
                except OSError:
                    continue
                rel = str(hook_file.relative_to(app_path))
                if "useQuery" not in content and "useMutation" not in content and "useInfiniteQuery" not in content:
                    violations.append(
                        Violation(
                            file=rel,
                            message="Hook file does not use useQuery/useMutation",
                            fix_hint="Use TanStack Query hooks",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
