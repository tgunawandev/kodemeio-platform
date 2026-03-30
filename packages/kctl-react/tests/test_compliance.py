"""Tests for compliance foundation — models, exceptions_map, engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kctl_react.core.compliance.engine import ComplianceEngine
from kctl_react.core.compliance.exceptions_map import APP_EXCEPTIONS, get_skip_providers
from kctl_react.core.compliance.fixes import apply_fixes
from kctl_react.core.compliance.models import (
    AppReport,
    CategoryResult,
    Violation,
    compute_grade,
)


# ---------------------------------------------------------------------------
# compute_grade
# ---------------------------------------------------------------------------


class TestComputeGrade:
    def test_a_plus(self) -> None:
        assert compute_grade(95) == "A+"
        assert compute_grade(100) == "A+"

    def test_a(self) -> None:
        assert compute_grade(90) == "A"
        assert compute_grade(94) == "A"

    def test_b(self) -> None:
        assert compute_grade(80) == "B"
        assert compute_grade(89) == "B"

    def test_c(self) -> None:
        assert compute_grade(70) == "C"
        assert compute_grade(79) == "C"

    def test_d(self) -> None:
        assert compute_grade(60) == "D"
        assert compute_grade(69) == "D"

    def test_f(self) -> None:
        assert compute_grade(0) == "F"
        assert compute_grade(59) == "F"


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------


class TestViolation:
    def test_defaults(self) -> None:
        v = Violation(file="src/App.tsx")
        assert v.line is None
        assert v.message == ""
        assert v.fix_hint is None
        assert v.auto_fixable is False

    def test_to_dict(self) -> None:
        v = Violation(
            file="src/App.tsx",
            line=10,
            message="Missing import",
            fix_hint="Add import",
            auto_fixable=True,
        )
        d = v.to_dict()
        assert d["file"] == "src/App.tsx"
        assert d["line"] == 10
        assert d["message"] == "Missing import"
        assert d["fix_hint"] == "Add import"
        assert d["auto_fixable"] is True


# ---------------------------------------------------------------------------
# CategoryResult
# ---------------------------------------------------------------------------


class TestCategoryResult:
    def test_score_no_violations(self) -> None:
        cat = CategoryResult(name="structure", label="File Structure", max_points=10)
        assert cat.score == 10

    def test_score_with_violations(self) -> None:
        cat = CategoryResult(
            name="structure",
            label="File Structure",
            max_points=10,
            violations=[Violation(file="a.tsx"), Violation(file="b.tsx")],
        )
        assert cat.score == 8

    def test_score_capped_at_zero(self) -> None:
        cat = CategoryResult(
            name="structure",
            label="File Structure",
            max_points=2,
            violations=[Violation(file=f"{i}.tsx") for i in range(5)],
        )
        assert cat.score == 0

    def test_to_dict(self) -> None:
        cat = CategoryResult(
            name="structure",
            label="File Structure",
            max_points=10,
            violations=[Violation(file="a.tsx", message="bad")],
        )
        d = cat.to_dict()
        assert d["name"] == "structure"
        assert d["label"] == "File Structure"
        assert d["max_points"] == 10
        assert d["score"] == 9
        assert len(d["violations"]) == 1


# ---------------------------------------------------------------------------
# AppReport
# ---------------------------------------------------------------------------


class TestAppReport:
    def _make_report(self) -> AppReport:
        return AppReport(
            app="sfa",
            categories=[
                CategoryResult(
                    name="structure",
                    label="File Structure",
                    max_points=10,
                    violations=[
                        Violation(file="a.tsx", auto_fixable=True),
                        Violation(file="b.tsx", auto_fixable=False),
                    ],
                ),
                CategoryResult(
                    name="imports",
                    label="Imports",
                    max_points=5,
                    violations=[Violation(file="c.tsx", auto_fixable=True)],
                ),
            ],
        )

    def test_total_score(self) -> None:
        r = self._make_report()
        assert r.total_score == (10 - 2) + (5 - 1)  # 8 + 4 = 12

    def test_max_score(self) -> None:
        r = self._make_report()
        assert r.max_score == 15

    def test_grade(self) -> None:
        r = self._make_report()
        pct = int(12 / 15 * 100)  # 80 -> B
        assert r.grade == "B"

    def test_grade_empty_report(self) -> None:
        r = AppReport(app="sfa")
        assert r.grade == "A+"

    def test_total_violations(self) -> None:
        r = self._make_report()
        assert r.total_violations == 3

    def test_auto_fixable_count(self) -> None:
        r = self._make_report()
        assert r.auto_fixable_count == 2

    def test_needs_review_count(self) -> None:
        r = self._make_report()
        assert r.needs_review_count == 1

    def test_to_dict(self) -> None:
        r = self._make_report()
        d = r.to_dict()
        assert d["app"] == "sfa"
        assert d["total_score"] == 12
        assert d["max_score"] == 15
        assert d["grade"] == "B"
        assert d["total_violations"] == 3
        assert len(d["categories"]) == 2


# ---------------------------------------------------------------------------
# exceptions_map
# ---------------------------------------------------------------------------


class TestExceptionsMap:
    def test_mrp_skips_gps(self) -> None:
        assert "GPSProvider" in get_skip_providers("mrp")

    def test_tpm_skips_gps(self) -> None:
        assert "GPSProvider" in get_skip_providers("tpm")

    def test_saas_skips_gps(self) -> None:
        assert "GPSProvider" in get_skip_providers("saas")

    def test_shop_skips_gps(self) -> None:
        assert "GPSProvider" in get_skip_providers("shop")

    def test_sfa_no_skip(self) -> None:
        assert get_skip_providers("sfa") == []

    def test_unknown_app_no_skip(self) -> None:
        assert get_skip_providers("unknown") == []

    def test_app_exceptions_keys(self) -> None:
        assert set(APP_EXCEPTIONS.keys()) == {"mrp", "tpm", "saas", "shop"}


# ---------------------------------------------------------------------------
# ComplianceEngine
# ---------------------------------------------------------------------------


class TestComplianceEngine:
    def test_audit_empty_checkers(self, tmp_path: Path) -> None:
        with patch("kctl_react.core.compliance.engine.CHECKER_MAP", {}):
            engine = ComplianceEngine()
            report = engine.audit(tmp_path, "sfa")
            assert report.app == "sfa"
            assert report.categories == []
            assert report.total_violations == 0
            assert report.grade == "A+"

    def test_audit_with_mock_checker(self, tmp_path: Path) -> None:
        def fake_checker(app_path: Path, app_name: str) -> CategoryResult:
            return CategoryResult(
                name="test",
                label="Test Category",
                max_points=10,
                violations=[Violation(file="x.tsx", message="issue")],
            )

        mock_map = {"test": fake_checker}
        with patch("kctl_react.core.compliance.engine.CHECKER_MAP", mock_map):
            engine = ComplianceEngine()
            report = engine.audit(tmp_path, "sfa")
            assert len(report.categories) == 1
            assert report.total_violations == 1
            assert report.total_score == 9

    def test_audit_filters_categories(self, tmp_path: Path) -> None:
        def checker_a(app_path: Path, app_name: str) -> CategoryResult:
            return CategoryResult(name="a", label="A", max_points=5)

        def checker_b(app_path: Path, app_name: str) -> CategoryResult:
            return CategoryResult(name="b", label="B", max_points=5)

        mock_map = {"a": checker_a, "b": checker_b}
        with patch("kctl_react.core.compliance.engine.CHECKER_MAP", mock_map):
            engine = ComplianceEngine()
            report = engine.audit(tmp_path, "sfa", categories=["a"])
            assert len(report.categories) == 1
            assert report.categories[0].name == "a"

    def test_generate_prompt_empty(self) -> None:
        engine = ComplianceEngine()
        report = AppReport(app="sfa")
        prompt = engine.generate_prompt(report)
        assert "# Fix Compliance Issues for `sfa`" in prompt
        assert "No auto-fixable issues found." in prompt
        assert "No manual review issues found." in prompt
        assert "kctl-react compliance audit sfa" in prompt

    def test_generate_prompt_with_violations(self) -> None:
        engine = ComplianceEngine()
        report = AppReport(
            app="wms",
            categories=[
                CategoryResult(
                    name="structure",
                    label="File Structure",
                    max_points=10,
                    violations=[
                        Violation(
                            file="src/App.tsx",
                            line=5,
                            message="Missing provider",
                            fix_hint="Add GPSProvider",
                            auto_fixable=True,
                        ),
                        Violation(
                            file="src/main.tsx",
                            line=12,
                            message="Wrong order",
                            fix_hint="Reorder providers",
                            auto_fixable=False,
                        ),
                    ],
                ),
            ],
        )
        prompt = engine.generate_prompt(report)
        assert "kctl-react compliance fix wms" in prompt
        assert "src/App.tsx" in prompt
        assert "Missing provider" in prompt
        assert "### File Structure" in prompt
        assert "Wrong order" in prompt


# ---------------------------------------------------------------------------
# apply_fixes (empty registry)
# ---------------------------------------------------------------------------


class TestApplyFixes:
    def test_empty_fixers(self, tmp_path: Path) -> None:
        with patch("kctl_react.core.compliance.fixes.ALL_FIXERS", {}):
            result = apply_fixes(tmp_path, "sfa")
            assert result == 0

    def test_empty_fixers_dry_run(self, tmp_path: Path) -> None:
        with patch("kctl_react.core.compliance.fixes.ALL_FIXERS", {}):
            result = apply_fixes(tmp_path, "sfa", dry_run=True)
            assert result == 0

    def test_with_mock_fixer(self, tmp_path: Path) -> None:
        def fake_fixer(app_path: Path, app_name: str, dry_run: bool = False) -> int:
            return 3

        with patch("kctl_react.core.compliance.fixes.ALL_FIXERS", {"structure": fake_fixer}):
            result = apply_fixes(tmp_path, "sfa")
            assert result == 3

    def test_category_filter(self, tmp_path: Path) -> None:
        def fixer_a(app_path: Path, app_name: str, dry_run: bool = False) -> int:
            return 2

        def fixer_b(app_path: Path, app_name: str, dry_run: bool = False) -> int:
            return 5

        with patch("kctl_react.core.compliance.fixes.ALL_FIXERS", {"a": fixer_a, "b": fixer_b}):
            result = apply_fixes(tmp_path, "sfa", categories=["a"])
            assert result == 2


# ---------------------------------------------------------------------------
# Checker imports
# ---------------------------------------------------------------------------

from kctl_react.core.compliance.checks import ALL_CHECKERS, CHECKER_MAP
from kctl_react.core.compliance.checks.darkmode import DarkmodeChecker
from kctl_react.core.compliance.checks.errors import ErrorsChecker
from kctl_react.core.compliance.checks.i18n_check import I18nChecker
from kctl_react.core.compliance.checks.imports import ImportsChecker
from kctl_react.core.compliance.checks.providers import ProviderChecker
from kctl_react.core.compliance.checks.shadcn import ShadcnChecker
from kctl_react.core.compliance.checks.structure import StructureChecker


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestCheckerRegistry:
    def test_all_checkers_count(self) -> None:
        assert len(ALL_CHECKERS) == 19

    def test_checker_map_count(self) -> None:
        assert len(CHECKER_MAP) == 19

    def test_all_checkers_have_required_attrs(self) -> None:
        for checker in ALL_CHECKERS:
            assert hasattr(checker, "name")
            assert hasattr(checker, "label")
            assert hasattr(checker, "max_points")
            assert hasattr(checker, "check")
            assert isinstance(checker.max_points, int)
            assert checker.max_points > 0

    def test_checker_map_keys_match(self) -> None:
        names = {c.name for c in ALL_CHECKERS}
        assert names == set(CHECKER_MAP.keys())

    def test_total_max_points(self) -> None:
        total = sum(c.max_points for c in ALL_CHECKERS)
        # 8+8+8+6+6+6+6+6+6+6+4+6+6+6+4+4+4+4+6 = 110
        assert total == 110


# ---------------------------------------------------------------------------
# StructureChecker
# ---------------------------------------------------------------------------


class TestStructureChecker:
    def test_all_missing(self, tmp_path: Path) -> None:
        checker = StructureChecker()
        result = checker.check(tmp_path, "sfa")
        assert result.name == "structure"
        assert result.max_points == 8
        # 11 dirs + 6 files + 1 .env.example = 18 violations
        assert len(result.violations) > 0

    def test_all_present(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        for d in [
            "api",
            "pages",
            "components",
            "config",
            "hooks",
            "contexts",
            "constants",
            "types",
            "i18n",
            "utils",
            "__tests__",
        ]:
            (src / d).mkdir(parents=True, exist_ok=True)
        for f in [
            "main.tsx",
            "App.tsx",
            "config/navConfig.tsx",
            "components/AppLayout.tsx",
            "api/client.ts",
            "types/api.ts",
        ]:
            (src / f).parent.mkdir(parents=True, exist_ok=True)
            (src / f).write_text("")
        (tmp_path / ".env.example").write_text("")
        checker = StructureChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0
        assert result.score == 8


# ---------------------------------------------------------------------------
# ProviderChecker
# ---------------------------------------------------------------------------


class TestProviderChecker:
    def test_no_main_tsx(self, tmp_path: Path) -> None:
        checker = ProviderChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 1
        assert "main.tsx not found" in result.violations[0].message

    def test_all_providers_present_correct_order(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        main_content = """
<ErrorBoundary>
  <PwaUpdatePrompt />
  <QueryClientProvider>
    <BrowserRouter>
      <AuthProvider>
        <GPSProvider>
          <TooltipProvider>
            <OfflineProvider>
              <AiProvider>
                <App />
              </AiProvider>
            </OfflineProvider>
          </TooltipProvider>
        </GPSProvider>
      </AuthProvider>
    </BrowserRouter>
  </QueryClientProvider>
</ErrorBoundary>
"""
        (src / "main.tsx").write_text(main_content)
        checker = ProviderChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_skip_gps_for_mrp(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        # No GPSProvider — should be ok for MRP
        main_content = """
<ErrorBoundary>
  <PwaUpdatePrompt />
  <QueryClientProvider>
    <BrowserRouter>
      <AuthProvider>
        <TooltipProvider>
          <OfflineProvider>
            <AiProvider>
              <App />
            </AiProvider>
          </OfflineProvider>
        </TooltipProvider>
      </AuthProvider>
    </BrowserRouter>
  </QueryClientProvider>
</ErrorBoundary>
"""
        (src / "main.tsx").write_text(main_content)
        checker = ProviderChecker()
        result = checker.check(tmp_path, "mrp")
        assert len(result.violations) == 0

    def test_wrong_order(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        # BrowserRouter before QueryClientProvider — wrong order
        main_content = """
<ErrorBoundary>
  <PwaUpdatePrompt />
  <BrowserRouter>
    <QueryClientProvider>
      <AuthProvider>
        <GPSProvider>
          <TooltipProvider>
            <OfflineProvider>
              <AiProvider>
                <App />
              </AiProvider>
            </OfflineProvider>
          </TooltipProvider>
        </GPSProvider>
      </AuthProvider>
    </QueryClientProvider>
  </BrowserRouter>
</ErrorBoundary>
"""
        (src / "main.tsx").write_text(main_content)
        checker = ProviderChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("order incorrect" in v.message for v in result.violations)


# ---------------------------------------------------------------------------
# ImportsChecker
# ---------------------------------------------------------------------------


class TestImportsChecker:
    def test_clean_code(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.tsx").write_text('import { Foo } from "@/components/Foo";')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_use_client(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.tsx").write_text('"use client";\nimport React from "react";')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert any('"use client"' in v.message for v in result.violations)
        assert result.violations[0].auto_fixable

    def test_deep_relative(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        pages = src / "pages"
        pages.mkdir(parents=True)
        (pages / "Foo.tsx").write_text('import { Bar } from "../../utils/bar";')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("Deep relative" in v.message for v in result.violations)

    def test_direct_generated_import(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        hooks = src / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "useStuff.ts").write_text('import { Foo } from "@/generated/types.gen";')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("@/generated/" in v.message for v in result.violations)

    def test_generated_import_ok_in_types_api(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        types_dir = src / "types"
        types_dir.mkdir(parents=True)
        (types_dir / "api.ts").write_text('export { Foo } from "@/generated/types.gen";')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_skips_tests(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        tests = src / "__tests__"
        tests.mkdir(parents=True)
        (tests / "App.test.tsx").write_text('"use client";\nconsole.log("test");')
        checker = ImportsChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# I18nChecker
# ---------------------------------------------------------------------------


class TestI18nChecker:
    def test_missing_files(self, tmp_path: Path) -> None:
        checker = I18nChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("Missing en.json" in v.message for v in result.violations)
        assert any("Missing id.json" in v.message for v in result.violations)

    def test_matching_keys(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"greeting": "Hello", "nav": {"home": "Home"}}')
        (i18n / "id.json").write_text('{"greeting": "Halo", "nav": {"home": "Beranda"}}')
        (i18n / "index.ts").write_text('import { createI18n } from "@kodemeio/core/i18n";')
        checker = I18nChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_missing_key_in_id(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"greeting": "Hello", "farewell": "Bye"}')
        (i18n / "id.json").write_text('{"greeting": "Halo"}')
        (i18n / "index.ts").write_text('import { createI18n } from "@kodemeio/core/i18n";')
        checker = I18nChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("farewell" in v.message for v in result.violations)
        assert any(v.auto_fixable for v in result.violations)

    def test_no_create_i18n(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text("{}")
        (i18n / "id.json").write_text("{}")
        (i18n / "index.ts").write_text('import i18n from "i18next";')
        checker = I18nChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("createI18n" in v.message for v in result.violations)


# ---------------------------------------------------------------------------
# ShadcnChecker
# ---------------------------------------------------------------------------


class TestShadcnChecker:
    def test_clean_code(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "pages").mkdir(parents=True)
        (src / "pages" / "Home.tsx").write_text("<Button onClick={handleClick}>Go</Button>")
        checker = ShadcnChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_raw_button(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "pages").mkdir(parents=True)
        (src / "pages" / "Home.tsx").write_text("<button onClick={handleClick}>Go</button>")
        checker = ShadcnChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("button" in v.message for v in result.violations)

    def test_skips_tests(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "pages" / "__tests__").mkdir(parents=True)
        (src / "pages" / "__tests__" / "Home.test.tsx").write_text("<button>test</button>")
        checker = ShadcnChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# DarkmodeChecker
# ---------------------------------------------------------------------------


class TestDarkmodeChecker:
    def test_clean_layout(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "components").mkdir(parents=True)
        (src / "components" / "AppLayout.tsx").write_text('import { ThemeToggle } from "@kodemeio/ui";')
        checker = DarkmodeChecker()
        result = checker.check(tmp_path, "sfa")
        assert not any("ThemeToggle" in v.message for v in result.violations)

    def test_no_violations_without_hardcoded_colors(self, tmp_path: Path) -> None:
        """ThemeToggle check is in theme checker; darkmode only checks colors."""
        src = tmp_path / "src"
        (src / "components").mkdir(parents=True)
        (src / "components" / "AppLayout.tsx").write_text("export function AppLayout() {}")
        checker = DarkmodeChecker()
        result = checker.check(tmp_path, "sfa")
        assert len(result.violations) == 0

    def test_hardcoded_colors(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "pages").mkdir(parents=True)
        (src / "pages" / "Home.tsx").write_text('<div className="bg-white text-black">stuff</div>')
        checker = DarkmodeChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("bg-white" in v.message for v in result.violations)
        assert any("text-black" in v.message for v in result.violations)


# ---------------------------------------------------------------------------
# ErrorsChecker
# ---------------------------------------------------------------------------


class TestErrorsChecker:
    def test_clean_main(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "main.tsx").write_text("ErrorBoundary Sentry.init getErrorMessage")
        checker = ErrorsChecker()
        result = checker.check(tmp_path, "sfa")
        assert not any("Missing" in v.message for v in result.violations)

    def test_missing_error_boundary(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "main.tsx").write_text("Sentry.init getErrorMessage")
        checker = ErrorsChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("ErrorBoundary" in v.message for v in result.violations)

    def test_bare_catch_console(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "main.tsx").write_text("ErrorBoundary Sentry.init getErrorMessage")
        (src / "utils").mkdir(parents=True)
        (src / "utils" / "helpers.ts").write_text("try { foo() } catch (e) { console.log(e) }")
        checker = ErrorsChecker()
        result = checker.check(tmp_path, "sfa")
        assert any("Bare catch" in v.message for v in result.violations)


# ---------------------------------------------------------------------------
# Fixer: structure_fix
# ---------------------------------------------------------------------------

from kctl_react.core.compliance.fixes.structure_fix import fix_structure
from kctl_react.core.compliance.checks.structure import REQUIRED_DIRS


class TestFixStructure:
    def test_creates_missing_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        count = fix_structure(tmp_path, "sfa")
        assert count == len(REQUIRED_DIRS)
        for d in REQUIRED_DIRS:
            assert (tmp_path / "src" / d).is_dir()

    def test_skips_existing_dirs(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        for d in REQUIRED_DIRS:
            (src / d).mkdir()
        count = fix_structure(tmp_path, "sfa")
        assert count == 0

    def test_partial_missing(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        # Create only first 3
        for d in REQUIRED_DIRS[:3]:
            (src / d).mkdir()
        count = fix_structure(tmp_path, "sfa")
        assert count == len(REQUIRED_DIRS) - 3

    def test_dry_run_no_side_effects(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        count = fix_structure(tmp_path, "sfa", dry_run=True)
        assert count == len(REQUIRED_DIRS)
        # No directories should be created in dry run
        for d in REQUIRED_DIRS:
            assert not (tmp_path / "src" / d).exists()


# ---------------------------------------------------------------------------
# Fixer: imports_fix
# ---------------------------------------------------------------------------

from kctl_react.core.compliance.fixes.imports_fix import fix_imports


class TestFixImports:
    def test_removes_use_client(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "App.tsx").write_text('"use client";\nimport React from "react";\n')
        count = fix_imports(tmp_path, "sfa")
        assert count == 1
        assert '"use client"' not in (src / "App.tsx").read_text()
        assert 'import React from "react";' in (src / "App.tsx").read_text()

    def test_removes_single_quote_variant(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "Foo.tsx").write_text("'use client'\nimport Foo from 'foo';\n")
        count = fix_imports(tmp_path, "sfa")
        assert count == 1
        assert "'use client'" not in (src / "Foo.tsx").read_text()

    def test_no_use_client(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "App.tsx").write_text('import React from "react";\n')
        count = fix_imports(tmp_path, "sfa")
        assert count == 0

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        nm = src / "node_modules" / "foo"
        nm.mkdir(parents=True)
        (nm / "index.tsx").write_text('"use client";\n')
        count = fix_imports(tmp_path, "sfa")
        assert count == 0

    def test_skips_generated(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        gen = src / "generated"
        gen.mkdir(parents=True)
        (gen / "types.gen.ts").write_text('"use client";\n')
        count = fix_imports(tmp_path, "sfa")
        assert count == 0

    def test_dry_run(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        original = '"use client";\nimport React from "react";\n'
        (src / "App.tsx").write_text(original)
        count = fix_imports(tmp_path, "sfa", dry_run=True)
        assert count == 1
        # File should remain unchanged
        assert (src / "App.tsx").read_text() == original

    def test_no_src_dir(self, tmp_path: Path) -> None:
        count = fix_imports(tmp_path, "sfa")
        assert count == 0


# ---------------------------------------------------------------------------
# Fixer: i18n_fix
# ---------------------------------------------------------------------------

from kctl_react.core.compliance.fixes.i18n_fix import fix_i18n


class TestFixI18n:
    def test_adds_missing_key_to_id(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"greeting": "Hello", "farewell": "Bye"}')
        (i18n / "id.json").write_text('{"greeting": "Halo"}')
        count = fix_i18n(tmp_path, "sfa")
        assert count == 1
        import json

        id_data = json.loads((i18n / "id.json").read_text())
        assert "farewell" in id_data
        assert id_data["farewell"] == ""

    def test_adds_missing_key_to_en(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"greeting": "Hello"}')
        (i18n / "id.json").write_text('{"greeting": "Halo", "extra": "Tambahan"}')
        count = fix_i18n(tmp_path, "sfa")
        assert count == 1
        import json

        en_data = json.loads((i18n / "en.json").read_text())
        assert "extra" in en_data
        assert en_data["extra"] == ""

    def test_nested_keys(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"nav": {"home": "Home", "about": "About"}}')
        (i18n / "id.json").write_text('{"nav": {"home": "Beranda"}}')
        count = fix_i18n(tmp_path, "sfa")
        assert count == 1
        import json

        id_data = json.loads((i18n / "id.json").read_text())
        assert id_data["nav"]["about"] == ""

    def test_already_synced(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        (i18n / "en.json").write_text('{"a": "1"}')
        (i18n / "id.json").write_text('{"a": "2"}')
        count = fix_i18n(tmp_path, "sfa")
        assert count == 0

    def test_missing_files(self, tmp_path: Path) -> None:
        count = fix_i18n(tmp_path, "sfa")
        assert count == 0

    def test_dry_run(self, tmp_path: Path) -> None:
        i18n = tmp_path / "src" / "i18n"
        i18n.mkdir(parents=True)
        en_text = '{"a": "1", "b": "2"}'
        id_text = '{"a": "X"}'
        (i18n / "en.json").write_text(en_text)
        (i18n / "id.json").write_text(id_text)
        count = fix_i18n(tmp_path, "sfa", dry_run=True)
        assert count == 1
        # Files should remain unchanged
        assert (i18n / "id.json").read_text() == id_text


# ---------------------------------------------------------------------------
# CLI command tests (Typer CliRunner)
# ---------------------------------------------------------------------------

import json as _json

from typer.testing import CliRunner

from kctl_react.cli import app as cli_app

# ---------------------------------------------------------------------------
# PracticesChecker — new checks
# ---------------------------------------------------------------------------


class TestPracticesProcessEnv:
    def test_detects_process_env(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "utils"
        src.mkdir(parents=True)
        (src / "config.ts").write_text("const url = process.env.API_URL;\n")
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert any("process.env" in v.message for v in result.violations)

    def test_import_meta_env_ok(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "utils"
        src.mkdir(parents=True)
        (src / "config.ts").write_text("const url = import.meta.env.VITE_API_URL;\n")
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert not any("process.env" in v.message for v in result.violations)


class TestPracticesLocalhostUrl:
    def test_detects_hardcoded_localhost(self, tmp_path: Path) -> None:
        pages = tmp_path / "src" / "pages"
        pages.mkdir(parents=True)
        (pages / "Foo.tsx").write_text('const API = "http://localhost:8069/api";\n')
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert any("localhost" in v.message for v in result.violations)

    def test_env_var_ok(self, tmp_path: Path) -> None:
        pages = tmp_path / "src" / "pages"
        pages.mkdir(parents=True)
        (pages / "Foo.tsx").write_text("const API = import.meta.env.VITE_API_BASE_URL;\n")
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert not any("localhost" in v.message for v in result.violations)


class TestPracticesWholeLibraryImport:
    def test_detects_whole_lodash_import(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "utils"
        src.mkdir(parents=True)
        (src / "helpers.ts").write_text('import _ from "lodash";\n')
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert any("Whole library" in v.message for v in result.violations)

    def test_named_import_ok(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "utils"
        src.mkdir(parents=True)
        (src / "helpers.ts").write_text('import { debounce } from "lodash";\n')
        from kctl_react.core.compliance.checks.practices import PracticesChecker

        result = PracticesChecker().check(tmp_path, "sfa")
        assert not any("Whole library" in v.message for v in result.violations)


_runner = CliRunner()


class TestComplianceAuditCLI:
    def test_audit_single_app(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "audit", "sfa"])
        assert result.exit_code == 0
        assert "Compliance Report: sfa" in result.output

    def test_audit_json(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--json", "--root", str(mock_monorepo), "compliance", "audit", "sfa"])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["app"] == "sfa"
        assert "categories" in data
        assert "grade" in data

    def test_audit_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "audit", "--all"])
        assert result.exit_code == 0
        assert "Scorecard" in result.output

    def test_audit_all_json(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--json", "--root", str(mock_monorepo), "compliance", "audit", "--all"])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 11
        app_names = [d["app"] for d in data]
        assert "sfa" in app_names

    def test_audit_min_score_pass(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "audit", "sfa", "--min-score", "0"]
        )
        assert result.exit_code == 0

    def test_audit_min_score_fail(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "audit", "sfa", "--min-score", "100"]
        )
        assert result.exit_code == 1

    def test_audit_no_app_no_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "audit"])
        assert result.exit_code == 1
        assert "Specify an app name or use --all" in result.output

    def test_audit_categories_filter(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(
            cli_app,
            ["--json", "--root", str(mock_monorepo), "compliance", "audit", "sfa", "--categories", "structure"],
        )
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert len(data["categories"]) == 1
        assert data["categories"][0]["name"] == "structure"


class TestComplianceFixCLI:
    def test_fix_dry_run(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "fix", "sfa", "--dry-run"])
        assert result.exit_code == 0
        assert "(dry-run)" in result.output.lower()

    def test_fix_no_app_no_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "fix"])
        assert result.exit_code == 1
        assert "Specify an app name or use --all" in result.output

    def test_fix_single_app(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "fix", "sfa"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_fix_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "fix", "--all"])
        assert result.exit_code == 0


class TestCompliancePromptCLI:
    def test_prompt_stdout(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "prompt", "sfa"])
        assert result.exit_code == 0
        assert "# Fix Compliance Issues for `sfa`" in result.output

    def test_prompt_output_file(self, mock_monorepo: Path, tmp_path: Path) -> None:
        dest = tmp_path / "out" / "fix-sfa.md"
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "prompt", "sfa", "-o", str(dest)])
        assert result.exit_code == 0
        assert dest.exists()
        content = dest.read_text()
        assert "# Fix Compliance Issues for `sfa`" in content

    def test_prompt_all_output_dir(self, mock_monorepo: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "prompts"
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "prompt", "--all", "-o", str(out_dir)]
        )
        assert result.exit_code == 0
        assert (out_dir / "fix-sfa.md").exists()
        assert (out_dir / "fix-saas.md").exists()

    def test_prompt_no_app_no_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "prompt"])
        assert result.exit_code == 1
        assert "Specify an app name or use --all" in result.output


# ---------------------------------------------------------------------------
# UiStandardChecker
# ---------------------------------------------------------------------------

from kctl_react.core.compliance.checks.ui_standard import UiStandardChecker


def _make_app(tmp_path: Path) -> Path:
    """Create a minimal app directory with required shared imports."""
    app = tmp_path / "myapp"
    src = app / "src"
    (src / "components").mkdir(parents=True)
    (src / "pages").mkdir(parents=True)
    # Provide a file that satisfies required shared component imports
    (src / "pages" / "Home.tsx").write_text(
        'import { PageHeader, Skeleton, EmptyState } from "@kodemeio/ui";\n'
        "export function Home() { return <PageHeader />; }\n"
    )
    return app


class TestUiStandardChecker:
    def test_no_violations_clean_app(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        assert result.name == "ui-standard"
        assert result.max_points == 6
        assert len(result.violations) == 0

    def test_detects_duplicate_button(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        (app / "src" / "components" / "Button.tsx").write_text("export function Button() {}")
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert any("Local duplicate of @kodemeio/ui component: Button.tsx" in m for m in msgs)

    def test_detects_duplicate_in_subdirectory(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        sub = app / "src" / "components" / "ui"
        sub.mkdir()
        (sub / "Dialog.tsx").write_text("export function Dialog() {}")
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert any("Dialog.tsx" in m for m in msgs)

    def test_missing_shared_imports(self, tmp_path: Path) -> None:
        app = tmp_path / "bare"
        src = app / "src"
        (src / "pages").mkdir(parents=True)
        (src / "components").mkdir(parents=True)
        (src / "pages" / "Home.tsx").write_text("export function Home() { return null; }\n")
        checker = UiStandardChecker()
        result = checker.check(app, "bare")
        msgs = [v.message for v in result.violations]
        assert any("PageHeader" in m for m in msgs)
        assert any("EmptyState" in m for m in msgs)

    def test_badge_wrapper_without_import(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        (app / "src" / "components" / "StatusBadge.tsx").write_text(
            "export function StatusBadge() { return <span>Active</span>; }\n"
        )
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert any("StatusBadge.tsx should use Badge from @kodemeio/ui" in m for m in msgs)

    def test_badge_wrapper_with_import_ok(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        (app / "src" / "components" / "StatusBadge.tsx").write_text(
            'import { Badge } from "@kodemeio/ui";\nexport function StatusBadge() { return <Badge>Active</Badge>; }\n'
        )
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert not any("StatusBadge.tsx" in m for m in msgs)

    def test_datatable_suggestion(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        pages = app / "src" / "pages"
        for name in ("Orders.tsx", "Products.tsx", "Users.tsx"):
            (pages / name).write_text(f"export function Page() {{ return <Table>data</Table>; }}\n")
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert any("3 table pages" in m for m in msgs)

    def test_datatable_no_false_positive(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        pages = app / "src" / "pages"
        for name in ("Orders.tsx", "Products.tsx", "Users.tsx"):
            (pages / name).write_text(f"export function Page() {{ return <Table>data</Table>; }}\n")
        # Add DataTable import somewhere
        (app / "src" / "components" / "List.tsx").write_text(
            'import { DataTable } from "@kodemeio/ui";\nexport function List() { return <DataTable />; }\n'
        )
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        msgs = [v.message for v in result.violations]
        assert not any("table pages" in m for m in msgs)

    def test_import_source_consistency(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)
        (app / "src" / "pages" / "Bad.tsx").write_text(
            'import { Button } from "../../packages/ui/src/button";\nexport function Bad() { return <Button />; }\n'
        )
        checker = UiStandardChecker()
        result = checker.check(app, "myapp")
        auto_fix = [v for v in result.violations if v.auto_fixable]
        assert len(auto_fix) >= 1
        assert any("Direct path import to packages/ui" in v.message for v in auto_fix)
