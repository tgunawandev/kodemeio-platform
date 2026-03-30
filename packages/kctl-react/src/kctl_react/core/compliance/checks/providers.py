"""Checker: provider stack order and completeness in main.tsx."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.exceptions_map import get_skip_providers
from kctl_react.core.compliance.models import CategoryResult, Violation

EXPECTED_ORDER = [
    "ErrorBoundary",
    "PwaUpdatePrompt",
    "QueryClientProvider",
    "BrowserRouter",
    "AuthProvider",
    "GPSProvider",
    "TooltipProvider",
    "OfflineProvider",
    "AiProvider",
    "App",
]


class ProviderChecker:
    name = "providers"
    label = "Provider Stack"
    max_points = 8

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        main_tsx = app_path / "src" / "main.tsx"

        if not main_tsx.is_file():
            violations.append(Violation(file="src/main.tsx", message="main.tsx not found"))
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        content = main_tsx.read_text()
        skip = get_skip_providers(app_name)
        expected = [p for p in EXPECTED_ORDER if p not in skip]

        # Find positions of each provider in the file
        positions: dict[str, int] = {}
        for provider in expected:
            # Match <Provider or <Provider> or {Provider}
            pattern = rf"<{provider}[\s>/]"
            match = re.search(pattern, content)
            if match:
                positions[provider] = match.start()

        # Check missing providers
        for provider in expected:
            if provider not in positions:
                violations.append(
                    Violation(
                        file="src/main.tsx",
                        message=f"Missing provider: {provider}",
                        fix_hint=f"Add <{provider}> to the provider stack",
                    )
                )

        # Check order of found providers
        found_ordered = sorted(positions.keys(), key=lambda p: positions[p])
        expected_found = [p for p in expected if p in positions]

        if found_ordered != expected_found:
            violations.append(
                Violation(
                    file="src/main.tsx",
                    message=f"Provider order incorrect. Expected: {' > '.join(expected_found)}, got: {' > '.join(found_ordered)}",
                    fix_hint="Reorder providers to match expected stack",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
