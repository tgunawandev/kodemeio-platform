"""ComplianceEngine — runs checkers and generates reports."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.checks import CHECKER_MAP
from kctl_react.core.compliance.models import AppReport, CategoryResult


class ComplianceEngine:
    """Runs compliance checkers and generates fix prompts."""

    def audit(
        self,
        app_path: Path,
        app_name: str,
        categories: list[str] | None = None,
    ) -> AppReport:
        """Run checkers (filtered by categories if given), return AppReport."""
        report = AppReport(app=app_name)

        if categories:
            checkers = [(name, fn) for name, fn in CHECKER_MAP.items() if name in categories]
        else:
            checkers = list(CHECKER_MAP.items())

        for _name, checker_fn in checkers:
            result: CategoryResult = checker_fn(app_path, app_name)
            report.categories.append(result)

        return report

    def generate_prompt(self, report: AppReport) -> str:
        """Generate markdown prompt for AI/human fixing."""
        pct = int(report.total_score / report.max_score * 100) if report.max_score > 0 else 100

        lines: list[str] = [
            f"# Fix Compliance Issues for `{report.app}`",
            "",
            f"- **App path**: `apps/{report.app}`",
            f"- **Score**: {report.total_score}/{report.max_score} ({pct}%)",
            f"- **Grade**: {report.grade}",
            f"- **Total issues**: {report.total_violations}",
            "",
        ]

        # Auto-fixable section
        auto_violations = [(c, v) for c in report.categories for v in c.violations if v.auto_fixable]
        lines.append("## Auto-fixable (run first)")
        lines.append("")
        if auto_violations:
            lines.append(f"```bash\nkctl-react compliance fix {report.app}\n```")
            lines.append("")
            for cat, v in auto_violations:
                hint = f" -- {v.fix_hint}" if v.fix_hint else ""
                lines.append(f"- `{v.file}`:{v.line or '?'} {v.message}{hint}")
        else:
            lines.append("No auto-fixable issues found.")
        lines.append("")

        # Manual review section
        manual_violations = [(c, v) for c in report.categories for v in c.violations if not v.auto_fixable]
        lines.append("## Issues Requiring Review")
        lines.append("")
        if manual_violations:
            current_cat = ""
            for cat, v in manual_violations:
                if cat.label != current_cat:
                    current_cat = cat.label
                    lines.append(f"### {current_cat}")
                    lines.append("")
                loc = f":{v.line}" if v.line else ""
                hint = f"\n  - Hint: {v.fix_hint}" if v.fix_hint else ""
                lines.append(f"- `{v.file}`{loc} {v.message}{hint}")
            lines.append("")
        else:
            lines.append("No manual review issues found.")
            lines.append("")

        # Verification section
        lines.append("## Verification")
        lines.append("")
        lines.append(f"```bash\nkctl-react compliance audit {report.app}\n```")
        lines.append("")

        return "\n".join(lines)
