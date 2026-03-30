"""Checker: dark mode support."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

HARDCODED_COLORS = re.compile(r"\b(?:bg-white|text-black|border-gray-\w+|bg-gray-\w+|text-gray-\w+)\b")


class DarkmodeChecker:
    name = "darkmode"
    label = "Dark Mode"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # ThemeToggle check is in theme checker — skip here to avoid duplicates

        # Scan pages/ and components/ for hardcoded colors
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
                    # Skip lines that have dark: variants — they handle dark mode
                    if "dark:" in line:
                        continue
                    matches = HARDCODED_COLORS.findall(line)
                    for m in matches:
                        violations.append(
                            Violation(
                                file=rel,
                                line=i,
                                message=f"Hardcoded color class: {m} — breaks dark mode",
                                fix_hint=f"Replace {m} with semantic token (e.g. bg-background, text-foreground)",
                            )
                        )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
