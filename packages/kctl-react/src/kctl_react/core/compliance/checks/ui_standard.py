"""Checker: UI standardization — shared component usage and import consistency."""

from __future__ import annotations

import re
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

# Components that should NOT exist locally — they are provided by @kodemeio/ui
SHARED_COMPONENTS = {
    "Button.tsx",
    "Input.tsx",
    "Textarea.tsx",
    "Label.tsx",
    "Select.tsx",
    "Badge.tsx",
    "Card.tsx",
    "Dialog.tsx",
    "Sheet.tsx",
    "Alert.tsx",
    "Table.tsx",
    "Tabs.tsx",
    "Tooltip.tsx",
    "Skeleton.tsx",
    "Progress.tsx",
    "Separator.tsx",
    "ScrollArea.tsx",
    "Checkbox.tsx",
    "Switch.tsx",
    "DropdownMenu.tsx",
    "Popover.tsx",
    "RadioGroup.tsx",
}

# Shared components every app should import from @kodemeio/ui
REQUIRED_SHARED = ["PageHeader", "LoadingSpinner", "Skeleton", "EmptyState"]

# Pattern for relative path imports to packages/ui
RELATIVE_UI_IMPORT = re.compile(r"""from\s+["']\.{1,3}/.*packages/ui""")


class UiStandardChecker:
    name = "ui-standard"
    label = "UI Standardization"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        src = app_path / "src"

        # 1. Duplicate components
        components_dir = src / "components"
        if components_dir.is_dir():
            for f in components_dir.rglob("*.tsx"):
                if f.name in SHARED_COMPONENTS:
                    rel = str(f.relative_to(app_path))
                    violations.append(
                        Violation(
                            file=rel,
                            message=f"Local duplicate of @kodemeio/ui component: {f.name}",
                            auto_fixable=False,
                        )
                    )

        # Collect all tsx files for subsequent checks
        all_tsx: list[Path] = []
        if src.is_dir():
            all_tsx = list(src.rglob("*.tsx"))
            all_tsx = [f for f in all_tsx if "__tests__" not in f.parts]

        all_contents: dict[Path, str] = {}
        for f in all_tsx:
            try:
                all_contents[f] = f.read_text()
            except OSError:
                continue

        # 2. Required shared component imports
        # Check LoadingSpinner OR Skeleton — either counts
        found_page_header = False
        found_loading = False
        found_empty_state = False

        for content in all_contents.values():
            if "@kodemeio/ui" in content:
                if "PageHeader" in content:
                    found_page_header = True
                if "LoadingSpinner" in content or "Skeleton" in content:
                    found_loading = True
                if "EmptyState" in content:
                    found_empty_state = True

        if not found_page_header:
            violations.append(
                Violation(
                    file="src/",
                    message="No usage of shared PageHeader from @kodemeio/ui",
                    fix_hint="Import PageHeader from @kodemeio/ui for consistent UX",
                )
            )
        if not found_loading:
            violations.append(
                Violation(
                    file="src/",
                    message="No usage of shared LoadingSpinner or Skeleton from @kodemeio/ui",
                    fix_hint="Import LoadingSpinner or Skeleton from @kodemeio/ui for consistent UX",
                )
            )
        if not found_empty_state:
            violations.append(
                Violation(
                    file="src/",
                    message="No usage of shared EmptyState from @kodemeio/ui",
                    fix_hint="Import EmptyState from @kodemeio/ui for consistent UX",
                )
            )

        # 3. Badge wrapper pattern
        if components_dir.is_dir():
            for f in components_dir.rglob("*.tsx"):
                name = f.stem  # e.g. "StatusBadge"
                if name.endswith("Badge") or name.endswith("StatusBadge"):
                    if f.name in SHARED_COMPONENTS:
                        continue  # already caught by check 1
                    try:
                        content = f.read_text()
                    except OSError:
                        continue
                    if "Badge" not in content or "@kodemeio/ui" not in content:
                        rel = str(f.relative_to(app_path))
                        violations.append(
                            Violation(
                                file=rel,
                                message=f"{f.name} should use Badge from @kodemeio/ui as base",
                            )
                        )

        # 4. DataTable usage
        table_page_count = 0
        has_datatable = False
        pages_dir = src / "pages"

        for f, content in all_contents.items():
            if "@kodemeio/ui" in content and "DataTable" in content:
                has_datatable = True

        if pages_dir.is_dir():
            for f in pages_dir.rglob("*.tsx"):
                if "__tests__" in f.parts:
                    continue
                content = all_contents.get(f, "")
                if "<Table" in content or "<table" in content:
                    table_page_count += 1

        if table_page_count >= 3 and not has_datatable:
            violations.append(
                Violation(
                    file="src/pages/",
                    message=f"App has {table_page_count} table pages but doesn't use DataTable from @kodemeio/ui",
                    fix_hint="Use DataTable from @kodemeio/ui for consistent table behavior",
                )
            )

        # 5. Import source consistency — relative path imports to packages/ui
        for f, content in all_contents.items():
            lines = content.splitlines()
            rel = str(f.relative_to(app_path))
            for i, line in enumerate(lines, 1):
                if RELATIVE_UI_IMPORT.search(line):
                    violations.append(
                        Violation(
                            file=rel,
                            line=i,
                            message="Direct path import to packages/ui — use @kodemeio/ui",
                            auto_fixable=True,
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
