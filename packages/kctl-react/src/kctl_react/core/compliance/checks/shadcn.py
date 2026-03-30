"""Checker: shadcn/ui component usage (no raw HTML elements)."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.analyzers import find_raw_html_elements
from kctl_react.core.compliance.models import CategoryResult, Violation


class ShadcnChecker:
    name = "shadcn"
    label = "shadcn/ui Usage"
    max_points = 8

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        for subdir in ("pages", "components"):
            scan_dir = src / subdir
            if not scan_dir.is_dir():
                continue
            for tsx_file in scan_dir.rglob("*.tsx"):
                # Skip test files
                if "__tests__" in tsx_file.parts:
                    continue
                results = find_raw_html_elements(tsx_file)
                for r in results:
                    # Skip title= prop on JSX components (title={...} is a
                    # component prop, not an HTML tooltip attribute)
                    if r["element"] == "title= attr":
                        code = str(r.get("code", ""))
                        if "title={" in code:
                            continue
                    rel = str(tsx_file.relative_to(app_path))
                    violations.append(
                        Violation(
                            file=rel,
                            line=int(r["line"]),
                            message=f"Raw <{r['element']}> — use {r['replacement']}",
                            fix_hint=f"Replace <{r['element']}> with {r['replacement']}",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
