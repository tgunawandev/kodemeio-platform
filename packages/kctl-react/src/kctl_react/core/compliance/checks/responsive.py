"""Checker: responsive layout setup."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


class ResponsiveChecker:
    name = "responsive"
    label = "Responsive Layout"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # AppLayout.tsx checks
        layout = src / "components" / "AppLayout.tsx"
        if layout.is_file():
            content = layout.read_text()
            for token in ("useIsMobile", "DesktopLayout", "MobileLayout"):
                if token not in content:
                    violations.append(
                        Violation(
                            file="src/components/AppLayout.tsx",
                            message=f"Missing {token} in AppLayout",
                            fix_hint=f"Add {token} for responsive switching",
                        )
                    )
        else:
            violations.append(
                Violation(
                    file="src/components/AppLayout.tsx",
                    message="Missing AppLayout.tsx",
                )
            )

        # navConfig.tsx checks are in navigation checker — skip here to avoid duplicates

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
