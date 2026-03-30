"""Checker: cross-app feature completeness."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

# Only features NOT already checked by other checkers:
# - ErrorBoundary, Sentry, getErrorMessage → errors checker
# - OfflineProvider, AiProvider, TooltipProvider → providers checker
# - PwaUpdatePrompt → pwa checker
MAIN_TSX_FEATURES = [
    "Toaster",
]

APP_TSX_FEATURES = [
    "DeepLinkHandler",
    "OfflineIndicator",
]


class FeaturesChecker:
    name = "features"
    label = "Cross-App Features"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []

        main_tsx = app_path / "src" / "main.tsx"
        if main_tsx.is_file():
            content = main_tsx.read_text()
            for feat in MAIN_TSX_FEATURES:
                if feat not in content:
                    violations.append(
                        Violation(
                            file="src/main.tsx",
                            message=f"Missing feature: {feat}",
                            fix_hint=f"Add {feat} to main.tsx",
                        )
                    )
        else:
            violations.append(Violation(file="src/main.tsx", message="main.tsx not found"))

        app_tsx = app_path / "src" / "App.tsx"
        if app_tsx.is_file():
            content = app_tsx.read_text()
            for feat in APP_TSX_FEATURES:
                if feat not in content:
                    violations.append(
                        Violation(
                            file="src/App.tsx",
                            message=f"Missing feature: {feat}",
                            fix_hint=f"Add {feat} to App.tsx",
                        )
                    )
        else:
            violations.append(Violation(file="src/App.tsx", message="App.tsx not found"))

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
