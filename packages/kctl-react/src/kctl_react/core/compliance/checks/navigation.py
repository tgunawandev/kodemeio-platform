"""Checker: navigation config and lazy loading."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


class NavigationChecker:
    name = "navigation"
    label = "Navigation"
    max_points = 4

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # navConfig.tsx must exist with expected exports
        nav = src / "config" / "navConfig.tsx"
        if nav.is_file():
            content = nav.read_text()
            for fn_name in ("useDesktopNavGroups", "useMobileNavItems"):
                if fn_name not in content:
                    violations.append(
                        Violation(
                            file="src/config/navConfig.tsx",
                            message=f"Missing {fn_name} in navConfig",
                            fix_hint=f"Export {fn_name} from navConfig.tsx",
                        )
                    )
        else:
            violations.append(
                Violation(
                    file="src/config/navConfig.tsx",
                    message="Missing navConfig.tsx",
                )
            )

        # App.tsx should use React.lazy() for pages
        app_tsx = src / "App.tsx"
        if app_tsx.is_file():
            content = app_tsx.read_text()
            # Check for non-lazy page imports (direct named imports from pages/)
            direct_imports = re.findall(r'import\s+\{[^}]+\}\s+from\s+["\']@/pages/', content)
            lazy_count = len(re.findall(r"React\.lazy\(|lazy\(\s*\(\)\s*=>", content))
            if direct_imports and lazy_count == 0:
                violations.append(
                    Violation(
                        file="src/App.tsx",
                        message="Pages imported directly without React.lazy()",
                        fix_hint="Use React.lazy(() => import('@/pages/...')) for code splitting",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
