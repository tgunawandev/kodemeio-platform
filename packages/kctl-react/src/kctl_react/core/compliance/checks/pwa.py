"""Checker: PWA configuration."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

PWA_META_TAGS = [
    "mobile-web-app-capable",
    "apple-mobile-web-app-capable",
    "viewport-fit=cover",
]


class PwaChecker:
    name = "pwa"
    label = "PWA Configuration"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []

        # index.html checks
        index_html = app_path / "index.html"
        if index_html.is_file():
            content = index_html.read_text()

            for tag in PWA_META_TAGS:
                if tag not in content:
                    violations.append(
                        Violation(
                            file="index.html",
                            message=f"Missing PWA meta tag: {tag}",
                            fix_hint=f"Add {tag} meta tag to index.html",
                        )
                    )

            if "manifest" not in content:
                violations.append(
                    Violation(
                        file="index.html",
                        message="Missing manifest reference in index.html",
                        fix_hint="Add <link rel='manifest' href='manifest.webmanifest'>",
                    )
                )
        else:
            violations.append(Violation(file="index.html", message="Missing index.html"))

        # Public icons
        public_dir = app_path / "public"
        if public_dir.is_dir():
            icon_files = (
                list(public_dir.glob("favicon*"))
                + list(public_dir.glob("icon*"))
                + list(public_dir.glob("*.png"))
                + list(public_dir.glob("*.svg"))
            )
            if not icon_files:
                violations.append(
                    Violation(
                        file="public/",
                        message="No icon files found in public/",
                        fix_hint="Add favicon and PWA icons to public/",
                    )
                )
        else:
            violations.append(
                Violation(
                    file="public/",
                    message="Missing public/ directory",
                )
            )

        # main.tsx PwaUpdatePrompt + useRegisterSW
        main_tsx = app_path / "src" / "main.tsx"
        if main_tsx.is_file():
            content = main_tsx.read_text()
            if "PwaUpdatePrompt" not in content:
                violations.append(
                    Violation(
                        file="src/main.tsx",
                        message="Missing PwaUpdatePrompt in main.tsx",
                        fix_hint="Add PwaUpdatePrompt component",
                    )
                )
            if "useRegisterSW" not in content:
                violations.append(
                    Violation(
                        file="src/main.tsx",
                        message="Missing useRegisterSW in main.tsx",
                        fix_hint="Add useRegisterSW from virtual:pwa-register/react",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
