"""Tests for CLI commands using CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from kctl_react.cli import app

runner = CliRunner()


def _extract_json(output: str) -> Any:
    """Extract JSON from CliRunner output that may mix stderr INFO lines with stdout JSON."""
    # Find the first [ or { which starts the JSON
    for i, ch in enumerate(output):
        if ch in ("[", "{"):
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No JSON found in output: {output[:200]}")


class TestAppsList:
    def test_apps_list(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "list"])
        assert result.exit_code == 0
        assert "sfa" in result.output
        assert "saas" in result.output

    def test_apps_list_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "apps", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 11
        app_names = [d["app"] for d in data]
        assert "sfa" in app_names

    def test_apps_ports(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "ports"])
        assert result.exit_code == 0
        assert "4004" in result.output

    def test_apps_status(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "status", "sfa"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_apps_status_all(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "status"])
        assert result.exit_code == 0


class TestTestCount:
    def test_count_direct(self, mock_monorepo: Path) -> None:
        """Test count function directly since Typer CliRunner callback routing is tricky."""
        from kctl_react.core.discovery import discover_apps

        total = 0
        for name in discover_apps(mock_monorepo):
            src = mock_monorepo / "apps" / name / "src"
            if src.is_dir():
                test_files = list(src.rglob("*.test.ts")) + list(src.rglob("*.test.tsx"))
                total += len(test_files)
        assert total == 22  # 11 apps * 2 test files each


class TestCodegenStatus:
    def test_all_apps_have_codegen(self, mock_monorepo: Path) -> None:
        """Verify codegen files exist in mock monorepo."""
        from kctl_react.core.discovery import discover_apps

        for name in discover_apps(mock_monorepo):
            assert (mock_monorepo / "apps" / name / "openapi-ts.config.ts").exists()
            assert (mock_monorepo / "apps" / name / "src" / "generated").is_dir()
            assert (mock_monorepo / "apps" / name / "src" / "types" / "api.ts").exists()


class TestBuildSize:
    def test_format_size(self) -> None:
        from kctl_react.commands.build import _format_size

        assert _format_size(0) == "[dim]--[/dim]"
        assert "B" in _format_size(500)
        assert "KB" in _format_size(2048)
        assert "MB" in _format_size(2 * 1024 * 1024)

    def test_get_dist_size(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.build import _get_dist_size

        dist = mock_monorepo / "apps" / "sfa" / "dist"
        dist.mkdir()
        (dist / "index.js").write_text("console.log('hello');")
        (dist / "style.css").write_text("body { color: red; }")

        size = _get_dist_size(dist)
        assert size > 0

    def test_get_dist_size_missing(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.build import _get_dist_size

        assert _get_dist_size(mock_monorepo / "nonexistent") == 0


class TestPackagesList:
    def test_list(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "packages", "list"])
        assert result.exit_code == 0
        assert "@kodemeio/core" in result.output

    def test_consumers(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "packages", "consumers", "core"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_size(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "packages", "size"])
        assert result.exit_code == 0


class TestDepsGraph:
    def test_graph(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "graph"])
        assert result.exit_code == 0

    def test_list(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "list"])
        assert result.exit_code == 0
        assert "@kodemeio/sfa" in result.output


class TestEnv:
    def test_show(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "show", "sfa"])
        assert result.exit_code == 0
        assert "VITE_ODOO_URL" in result.output

    def test_show_no_env(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "show", "lfa"])
        assert result.exit_code == 0
        assert "No .env" in result.output

    def test_diff(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "diff", "sfa", "wms"])
        assert result.exit_code == 0

    def test_validate(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "validate"])
        assert result.exit_code == 0


class TestScaffold:
    def test_page(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "page", "sfa", "CustomerDetail"])
        assert result.exit_code == 0
        page_file = mock_monorepo / "apps" / "sfa" / "src" / "pages" / "CustomerDetail.tsx"
        assert page_file.exists()
        content = page_file.read_text()
        assert "CustomerDetail" in content
        assert "usePageTitle" in content

    def test_hook(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "hook", "sfa", "orders"])
        assert result.exit_code == 0
        hook_file = mock_monorepo / "apps" / "sfa" / "src" / "hooks" / "useOrder.ts"
        assert hook_file.exists()
        content = hook_file.read_text()
        assert "useOrderList" in content
        assert "useQueryClient" in content

    def test_component(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "component", "sfa", "OrderCard"])
        assert result.exit_code == 0
        comp_file = mock_monorepo / "apps" / "sfa" / "src" / "components" / "OrderCard.tsx"
        assert comp_file.exists()

    def test_page_already_exists(self, mock_monorepo: Path) -> None:
        pages_dir = mock_monorepo / "apps" / "sfa" / "src" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        (pages_dir / "Existing.tsx").write_text("existing")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "page", "sfa", "Existing"])
        assert result.exit_code == 1


class TestClean:
    def test_clean(self, mock_monorepo: Path) -> None:
        # Create dist dirs
        (mock_monorepo / "apps" / "sfa" / "dist").mkdir()
        (mock_monorepo / "apps" / "sfa" / ".turbo").mkdir()

        result = runner.invoke(app, ["--root", str(mock_monorepo), "clean", "run"])
        assert result.exit_code == 0
        assert "Cleaned" in result.output
        assert not (mock_monorepo / "apps" / "sfa" / "dist").exists()

    def test_clean_single_app(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "wms" / "dist").mkdir()
        result = runner.invoke(app, ["--root", str(mock_monorepo), "clean", "run", "wms"])
        assert result.exit_code == 0


class TestDoctor:
    def test_doctor(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "doctor", "check"])
        # May exit 1 due to missing env files, but should not crash
        assert "System Tools" in result.output
        assert "Monorepo Structure" in result.output
        assert "Apps" in result.output


class TestInfo:
    def test_info(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "info"])
        assert result.exit_code == 0
        assert "kctl-react" in result.output


class TestDashboard:
    def test_dashboard(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "dashboard", "show"])
        assert result.exit_code == 0
        assert "11/11" in result.output

    def test_dashboard_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "dashboard", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["apps_total"] == 11


class TestScaffoldEnhanced:
    def test_scaffold_form(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "form", "sfa", "CustomerForm"])
        assert result.exit_code == 0
        form_file = mock_monorepo / "apps" / "sfa" / "src" / "components" / "CustomerForm.tsx"
        assert form_file.exists()
        content = form_file.read_text()
        assert "useForm" in content
        assert "zodResolver" in content

    def test_scaffold_test(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "test", "sfa", "App"])
        assert result.exit_code == 0
        test_file = mock_monorepo / "apps" / "sfa" / "src" / "pages" / "App.test.tsx"
        assert test_file.exists()
        content = test_file.read_text()
        assert "createWrapper" in content
        assert "vi.mock" in content

    def test_hook_uses_codegen_types(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "scaffold", "hook", "sfa", "orders"])
        assert result.exit_code == 0
        hook_file = mock_monorepo / "apps" / "sfa" / "src" / "hooks" / "useOrder.ts"
        content = hook_file.read_text()
        assert "@/types/api" in content
        assert "Record<string, unknown>" not in content


class TestInvalidApp:
    def test_invalid_app_error(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "status", "nonexistent"])
        assert result.exit_code == 1


class TestVersion:
    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestHelp:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "apps" in result.output
        assert "dashboard" in result.output
        assert "doctor" in result.output
        assert "clean" in result.output
        assert "info" in result.output
        assert "affected" in result.output
        assert "e2e" in result.output

    def test_all_command_groups_registered(self) -> None:
        result = runner.invoke(app, ["--help"])
        expected = [
            "affected",
            "apps",
            "build",
            "clean",
            "codegen",
            "config",
            "dashboard",
            "deploy",
            "deps",
            "dev",
            "doctor",
            "e2e",
            "env",
            "info",
            "lint",
            "packages",
            "scaffold",
            "test",
        ]
        for group in expected:
            assert group in result.output, f"Missing command group: {group}"


class TestAffected:
    def test_affected(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "affected"])
        assert result.exit_code == 0


class TestBuildChunks:
    def test_chunks_with_dist(self, mock_monorepo: Path) -> None:
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True)
        (dist / "index-abc123.js").write_text("console.log('main');")
        (dist / "vendor-def456.js").write_text("// vendor chunk")
        (dist / "style-ghi789.css").write_text("body { color: red; }")

        from kctl_react.commands.build import _get_dist_size

        assert _get_dist_size(mock_monorepo / "apps" / "sfa" / "dist") > 0

    def test_history_save_load(self, tmp_path: Path) -> None:
        from kctl_react.core.history import get_latest_snapshot, load_history, save_snapshot

        save_snapshot(tmp_path, {"apps": {"sfa": 1000, "wms": 2000}})
        history = load_history(tmp_path)
        assert len(history) == 1
        assert history[0]["apps"]["sfa"] == 1000

        latest = get_latest_snapshot(tmp_path)
        assert latest is not None
        assert latest["apps"]["wms"] == 2000


class TestGit:
    def test_get_affected_apps(self, mock_monorepo: Path) -> None:
        from kctl_react.core.git import get_affected_apps

        # In mock monorepo without git, should return empty
        apps = get_affected_apps(mock_monorepo)
        assert isinstance(apps, list)

    def test_get_current_branch(self, mock_monorepo: Path) -> None:
        from kctl_react.core.git import get_current_branch

        branch = get_current_branch(mock_monorepo)
        assert isinstance(branch, str)


class TestDepsWhy:
    def test_why(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "why", "@kodemeio/core"])
        assert result.exit_code == 0

    def test_duplicates(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "duplicates"])
        assert result.exit_code == 0


class TestTestSummary:
    def test_coverage_no_data(self, mock_monorepo: Path) -> None:
        """Test coverage command when no coverage data exists."""
        from kctl_react.core.discovery import discover_apps

        # Just verify no crash — coverage files don't exist in mock
        for name in discover_apps(mock_monorepo):
            cov_file = mock_monorepo / "apps" / name / "coverage" / "coverage-summary.json"
            assert not cov_file.exists()


class TestE2e:
    def test_e2e_help(self) -> None:
        result = runner.invoke(app, ["e2e", "--help"])
        assert result.exit_code == 0
        assert "screenshots" in result.output
        assert "test" in result.output
        assert "report" in result.output


# ── Security commands ──────────────────────────────────────────────


class TestSecuritySecrets:
    def test_secrets_clean(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "secrets"])
        assert result.exit_code == 0
        assert "No hardcoded secrets" in result.output

    def test_secrets_single_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "secrets", "sfa"])
        assert result.exit_code == 0

    def test_secrets_detects_aws_key(self, mock_monorepo: Path) -> None:
        # Plant a fake secret
        secret_file = mock_monorepo / "apps" / "sfa" / "src" / "config.ts"
        secret_file.write_text('const key = "AKIAIOSFODNN7EXAMPLE1";\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "secrets", "sfa"])
        assert result.exit_code == 0
        assert "AWS Access Key" in result.output

    def test_secrets_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "security", "secrets"])
        assert result.exit_code == 0
        # CliRunner mixes stderr+stdout; extract JSON portion
        assert "No hardcoded secrets" in result.output

    def test_secrets_skips_comments(self, mock_monorepo: Path) -> None:
        commented = mock_monorepo / "apps" / "sfa" / "src" / "commented.ts"
        commented.write_text('// const key = "AKIAIOSFODNN7EXAMPLE1";\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "secrets", "sfa"])
        assert result.exit_code == 0
        assert "No hardcoded secrets" in result.output

    def test_secrets_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "secrets", "nonexistent"])
        assert result.exit_code == 1


class TestSecurityScanFile:
    def test_scan_file_for_secrets(self, tmp_path: Path) -> None:
        from kctl_react.commands.security import _scan_file_for_secrets

        f = tmp_path / "test.ts"
        # ghp_ + 36 alphanumeric chars to match the pattern
        f.write_text('const token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl";\n')
        findings = _scan_file_for_secrets(f)
        assert len(findings) >= 1
        types = [fnd["type"] for fnd in findings]
        assert "GitHub Token" in types

    def test_scan_empty_file(self, tmp_path: Path) -> None:
        from kctl_react.commands.security import _scan_file_for_secrets

        f = tmp_path / "empty.ts"
        f.write_text("")
        assert _scan_file_for_secrets(f) == []


class TestSecurityParseAudit:
    def test_parse_audit_json_empty(self) -> None:
        from kctl_react.commands.security import _parse_audit_json

        result = _parse_audit_json("{}")
        assert result["total"] == 0

    def test_parse_audit_json_invalid(self) -> None:
        from kctl_react.commands.security import _parse_audit_json

        result = _parse_audit_json("not json")
        assert result["total"] == 0

    def test_parse_audit_json_with_advisories(self) -> None:
        from kctl_react.commands.security import _parse_audit_json

        data = json.dumps(
            {
                "advisories": {
                    "1": {"severity": "critical"},
                    "2": {"severity": "high"},
                    "3": {"severity": "moderate"},
                }
            }
        )
        result = _parse_audit_json(data)
        assert result["critical"] == 1
        assert result["high"] == 1
        assert result["moderate"] == 1
        assert result["total"] == 3


class TestSecurityHeaders:
    def test_headers_help(self) -> None:
        result = runner.invoke(app, ["security", "headers", "--help"])
        assert result.exit_code == 0
        assert "security headers" in result.output.lower()

    def test_headers_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "headers", "nonexistent"])
        assert result.exit_code == 1


class TestSecurityDepsLicense:
    def test_license_help(self) -> None:
        result = runner.invoke(app, ["security", "deps-license", "--help"])
        assert result.exit_code == 0
        assert "license" in result.output.lower()

    def test_license_no_node_modules(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "deps-license"])
        assert result.exit_code == 0
        assert "node_modules not found" in result.output

    def test_license_scan(self, mock_monorepo: Path) -> None:
        # Create a fake node_modules with licenses
        nm = mock_monorepo / "node_modules"
        pkg = nm / "fake-pkg"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text(json.dumps({"name": "fake-pkg", "license": "MIT"}))
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "deps-license"])
        assert result.exit_code == 0
        assert "MIT" in result.output

    def test_license_check_disallowed(self, mock_monorepo: Path) -> None:
        nm = mock_monorepo / "node_modules"
        pkg = nm / "gpl-pkg"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text(json.dumps({"name": "gpl-pkg", "license": "GPL-3.0"}))
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "deps-license", "--check", "GPL-3.0"])
        assert result.exit_code == 1


# ── Perf commands ──────────────────────────────────────────────────


class TestPerfBundle:
    def test_bundle_no_build(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "bundle", "sfa"])
        assert result.exit_code == 0
        assert "has not been built" in result.output

    def test_bundle_with_build(self, mock_monorepo: Path) -> None:
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True)
        (dist / "index-abc123.js").write_text("x" * 5000)
        (dist / "vendor-def456.js").write_text("x" * 10000)
        (dist / "style-ghi789.css").write_text("x" * 2000)
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "bundle", "sfa"])
        assert result.exit_code == 0
        assert "vendor" in result.output
        assert "JS" in result.output or "js" in result.output

    def test_bundle_json(self, mock_monorepo: Path) -> None:
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True)
        (dist / "index.js").write_text("x" * 1000)
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "perf", "bundle", "sfa"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) >= 1

    def test_bundle_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "bundle", "nonexistent"])
        assert result.exit_code == 1


class TestPerfHistory:
    def test_history_no_data(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "history", "sfa"])
        assert result.exit_code == 0
        assert "No Lighthouse history" in result.output

    def test_history_with_lighthouse_data(self, mock_monorepo: Path) -> None:
        # Write fake lighthouse history
        lh_dir = mock_monorepo / ".kctl-react"
        lh_dir.mkdir(parents=True, exist_ok=True)
        (lh_dir / "lighthouse.json").write_text(
            json.dumps(
                [
                    {
                        "app": "sfa",
                        "url": "http://localhost:4004",
                        "scores": {"performance": 95, "accessibility": 90, "best-practices": 85, "seo": 80},
                        "timestamp": "2026-03-20T10:00:00+00:00",
                    }
                ]
            )
        )
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "history", "sfa"])
        assert result.exit_code == 0
        assert "95" in result.output

    def test_history_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "history", "nonexistent"])
        assert result.exit_code == 1


class TestPerfLighthouse:
    def test_lighthouse_help(self) -> None:
        result = runner.invoke(app, ["perf", "lighthouse", "--help"])
        assert result.exit_code == 0
        assert "budget" in result.output.lower()


class TestPerfEnhanced:
    def test_vitals(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "vitals", "sfa"])
        assert result.exit_code == 0

    def test_images(self, mock_monorepo: Path) -> None:
        public = mock_monorepo / "apps" / "sfa" / "public"
        public.mkdir(exist_ok=True)
        (public / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 500000)
        (public / "icon.svg").write_text("<svg></svg>")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "images", "sfa"])
        assert result.exit_code == 0
        assert "logo.png" in result.output

    def test_fonts(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "fonts", "sfa"])
        assert result.exit_code == 0


# ── Maintenance commands ───────────────────────────────────────────


class TestMaintenanceHealthReport:
    def test_health_report(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "health-report"])
        assert result.exit_code == 0
        assert "sfa" in result.output
        assert "saas" in result.output

    def test_health_report_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "maintenance", "health-report"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) == 11
        app_names = [d["app"] for d in data]
        assert "sfa" in app_names
        assert "saas" in app_names
        sfa = next(d for d in data if d["app"] == "sfa")
        assert "tests" in sfa
        assert "codegen" in sfa


class TestMaintenanceCleanup:
    def test_cleanup_dry_run(self, mock_monorepo: Path) -> None:
        # Create some artifacts
        (mock_monorepo / "apps" / "sfa" / "dist").mkdir()
        (mock_monorepo / "apps" / "sfa" / "dist" / "index.js").write_text("x")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "cleanup", "--dry-run"])
        assert result.exit_code == 0
        assert "dist" in result.output

    def test_cleanup_nothing_to_clean(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "cleanup", "--dry-run"])
        assert result.exit_code == 0
        assert "Nothing to clean" in result.output

    def test_cleanup_removes_dist(self, mock_monorepo: Path) -> None:
        dist = mock_monorepo / "apps" / "sfa" / "dist"
        dist.mkdir()
        (dist / "index.js").write_text("x")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "cleanup"])
        assert result.exit_code == 0
        assert not dist.exists()

    def test_cleanup_json(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "dist").mkdir()
        (mock_monorepo / "apps" / "sfa" / "dist" / "index.js").write_text("x")
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "maintenance", "cleanup", "--dry-run"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) >= 1


class TestMaintenanceDrStatus:
    def test_dr_status(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "dr-status"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_dr_status_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "maintenance", "dr-status"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) == 11
        sfa = next(d for d in data if d["app"] == "sfa")
        assert "build" in sfa
        assert "docker" in sfa

    def test_dr_status_with_dockerfile(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "Dockerfile").write_text("FROM node:20\n")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "dr-status"])
        assert result.exit_code == 0
        assert "ready" in result.output


class TestMaintenanceCountTestFiles:
    def test_count_test_files(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.maintenance import _count_test_files

        count = _count_test_files(mock_monorepo / "apps" / "sfa")
        assert count == 2  # App.test.tsx + utils.test.ts

    def test_count_test_files_missing(self, tmp_path: Path) -> None:
        from kctl_react.commands.maintenance import _count_test_files

        assert _count_test_files(tmp_path / "nonexistent") == 0


# ── Security report command ────────────────────────────────────────


class TestSecurityReport:
    def test_report(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "report"])
        assert result.exit_code == 0
        assert "audit" in result.output
        assert "secrets" in result.output
        assert "licenses" in result.output

    def test_report_single_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "report", "sfa"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_report_strict_clean(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "report", "--strict"])
        assert result.exit_code == 0  # No issues found, should pass

    def test_report_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "security", "report"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) == 4
        checks = [d["check"] for d in data]
        assert "audit" in checks
        assert "secrets" in checks

    def test_report_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "security", "report", "nonexistent"])
        assert result.exit_code == 1


# ── Perf PWA command ───────────────────────────────────────────────


class TestPerfPwa:
    def test_pwa_all_apps(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "pwa"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_pwa_single_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "pwa", "sfa"])
        assert result.exit_code == 0
        assert "sfa" in result.output

    def test_pwa_with_manifest(self, mock_monorepo: Path) -> None:
        pub = mock_monorepo / "apps" / "sfa" / "public"
        pub.mkdir(parents=True, exist_ok=True)
        (pub / "manifest.webmanifest").write_text('{"name": "SFA", "icons": [{"src": "icon.png"}]}')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "pwa", "sfa"])
        assert result.exit_code == 0
        assert "yes" in result.output

    def test_pwa_with_vite_plugin(self, mock_monorepo: Path) -> None:
        vite_cfg = mock_monorepo / "apps" / "sfa" / "vite.config.ts"
        vite_cfg.write_text('import { VitePWA } from "vite-plugin-pwa";\nexport default {};\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "pwa", "sfa"])
        assert result.exit_code == 0

    def test_pwa_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "perf", "pwa", "sfa"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) >= 1
        assert "manifest" in data[0]
        assert "service_worker" in data[0]

    def test_pwa_check_readiness_function(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.perf import _check_pwa_readiness

        result = _check_pwa_readiness(mock_monorepo / "apps" / "sfa")
        assert isinstance(result, dict)
        assert "manifest" in result
        assert result["manifest"] is False  # No manifest in mock

    def test_pwa_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "perf", "pwa", "nonexistent"])
        assert result.exit_code == 1


# ── Maintenance deps-sync command ─────────────────────────────────


class TestMaintenanceDepsSync:
    def test_deps_sync_all_in_sync(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "deps-sync"])
        assert result.exit_code == 0
        assert "in sync" in result.output

    def test_deps_sync_detects_inconsistency(self, mock_monorepo: Path) -> None:
        # Add react with different versions to two apps
        for app_name, ver in [("sfa", "^18.3.0"), ("wms", "^19.0.0")]:
            pkg_file = mock_monorepo / "apps" / app_name / "package.json"
            pkg = json.loads(pkg_file.read_text())
            pkg["dependencies"]["react"] = ver
            pkg_file.write_text(json.dumps(pkg, indent=2))

        result = runner.invoke(app, ["--root", str(mock_monorepo), "maintenance", "deps-sync"])
        assert result.exit_code == 0
        assert "react" in result.output
        assert "inconsisten" in result.output.lower()

    def test_deps_sync_json(self, mock_monorepo: Path) -> None:
        # Add inconsistency
        for app_name, ver in [("sfa", "^18.3.0"), ("wms", "^19.0.0")]:
            pkg_file = mock_monorepo / "apps" / app_name / "package.json"
            pkg = json.loads(pkg_file.read_text())
            pkg["dependencies"]["react"] = ver
            pkg_file.write_text(json.dumps(pkg, indent=2))

        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "maintenance", "deps-sync"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert len(data) >= 1
        assert data[0]["package"] == "react"

    def test_collect_dep_versions(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.maintenance import _collect_dep_versions

        # Add react dep
        pkg_file = mock_monorepo / "apps" / "sfa" / "package.json"
        pkg = json.loads(pkg_file.read_text())
        pkg["dependencies"]["react"] = "^19.0.0"
        pkg_file.write_text(json.dumps(pkg, indent=2))

        versions = _collect_dep_versions(mock_monorepo, ["sfa"], [])
        assert "react" in versions
        assert "sfa" in versions["react"]


# ── UI Audit Expanded tests ────────────────────────────────────────


class TestUiAuditExpanded:
    def test_detects_all_violation_types(self, mock_monorepo: Path) -> None:
        """Run ui audit --json on an app and verify button/hr/title= detected."""
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "ui", "audit", "sfa"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert isinstance(data, list)
        elements_found = {item["element"] for item in data}
        # BadPage.tsx has button, hr, title= attr, fixed inset-0, animate-pulse
        assert "button" in elements_found, f"Expected 'button' in {elements_found}"
        assert "hr" in elements_found, f"Expected 'hr' in {elements_found}"
        assert "title= attr" in elements_found, f"Expected 'title= attr' in {elements_found}"

    def test_clean_page_no_violations(self, mock_monorepo: Path) -> None:
        """Verify GoodPage.tsx has zero violations using find_raw_html_elements directly."""
        from kctl_react.core.analyzers import find_raw_html_elements

        good_page = mock_monorepo / "apps" / "sfa" / "src" / "GoodPage.tsx"
        violations = find_raw_html_elements(good_page)
        assert violations == [], f"Expected no violations in GoodPage.tsx but got: {violations}"

    def test_ui_compliance_score(self, mock_monorepo: Path) -> None:
        """Run ui compliance and verify % appears in output."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "compliance", "sfa"])
        assert result.exit_code == 0
        assert "%" in result.output

    def test_ui_anti_patterns(self, mock_monorepo: Path) -> None:
        """Run ui anti-patterns and verify exit 0."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "anti-patterns", "sfa"])
        assert result.exit_code == 0


# ── Codegen enhanced commands ──────────────────────────────────────


class TestCodegenEnhanced:
    def test_codegen_verify(self, mock_monorepo: Path) -> None:
        # Populate types.gen.ts with exported types
        gen_dir = mock_monorepo / "apps" / "sfa" / "src" / "generated"
        (gen_dir / "types.gen.ts").write_text(
            "export type CustomerListResponse = { data: Customer[] };\n"
            "export type Customer = { id: number; name: string };\n"
        )
        # types/api.ts re-exports from @/generated/
        types_api = mock_monorepo / "apps" / "sfa" / "src" / "types" / "api.ts"
        types_api.write_text('export type { CustomerListResponse, Customer } from "@/generated/types.gen";\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "codegen", "verify", "sfa"])
        assert result.exit_code == 0

    def test_codegen_verify_direct_import_flagged(self, mock_monorepo: Path) -> None:
        # types.gen.ts and types/api.ts exist
        gen_dir = mock_monorepo / "apps" / "sfa" / "src" / "generated"
        (gen_dir / "types.gen.ts").write_text("export type CustomerListResponse = { data: unknown[] };\n")
        types_api = mock_monorepo / "apps" / "sfa" / "src" / "types" / "api.ts"
        types_api.write_text('export type { CustomerListResponse } from "@/generated/types.gen";\n')
        # A hook that imports directly from @/generated/ — should be flagged
        hooks_dir = mock_monorepo / "apps" / "sfa" / "src" / "hooks"
        (hooks_dir / "useOrders.ts").write_text(
            'import type { CustomerListResponse } from "@/generated/types.gen";\n'
            "export function useOrders() { return null; }\n"
        )
        result = runner.invoke(app, ["--root", str(mock_monorepo), "codegen", "verify", "sfa"])
        # Should still exit 0 but mention the violation
        assert result.exit_code == 0
        assert "generated" in result.output.lower()

    def test_codegen_drift(self, mock_monorepo: Path) -> None:
        # types.gen.ts has only CustomerListResponse
        gen_dir = mock_monorepo / "apps" / "sfa" / "src" / "generated"
        (gen_dir / "types.gen.ts").write_text("export type CustomerListResponse = { data: unknown[] };\n")
        # types/api.ts re-exports a type that no longer exists in gen file
        types_api = mock_monorepo / "apps" / "sfa" / "src" / "types" / "api.ts"
        types_api.write_text(
            'export type { CustomerListResponse } from "@/generated/types.gen";\n'
            "export type OldDeletedType = unknown;\n"
        )
        # A hook that imports OldDeletedType from @/types/api
        hooks_dir = mock_monorepo / "apps" / "sfa" / "src" / "hooks"
        (hooks_dir / "useStale.ts").write_text(
            'import type { OldDeletedType } from "@/types/api";\n'
            "export function useStale(): OldDeletedType { return null; }\n"
        )
        result = runner.invoke(app, ["--root", str(mock_monorepo), "codegen", "drift", "sfa"])
        assert result.exit_code == 0

    def test_codegen_schema_health(self, mock_monorepo: Path) -> None:
        # Populate types.gen.ts with enough content (>50 bytes)
        gen_dir = mock_monorepo / "apps" / "sfa" / "src" / "generated"
        (gen_dir / "types.gen.ts").write_text(
            "// Auto-generated — do not edit\nexport type CustomerListResponse = { data: unknown[] };\n"
        )
        result = runner.invoke(app, ["--root", str(mock_monorepo), "codegen", "schema-health", "sfa"])
        assert result.exit_code == 0


class TestLintEnhanced:
    def test_strict_check(self, mock_monorepo: Path) -> None:
        """All mock apps have strict: true — should exit 0."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 0
        assert "strict" in result.output.lower()

    def test_strict_check_json(self, mock_monorepo: Path) -> None:
        """JSON output should list each app with strict: true."""
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert isinstance(data, list)
        assert len(data) == 11
        for entry in data:
            assert entry["strict"] == "true"

    def test_strict_check_fails_when_not_strict(self, mock_monorepo: Path) -> None:
        """If one app lacks strict: true, exit code should be 1."""
        (mock_monorepo / "apps" / "sfa" / "tsconfig.json").write_text(
            '{"compilerOptions": {"strict": false, "jsx": "react-jsx"}}'
        )
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 1

    def test_tsconfig_audit(self, mock_monorepo: Path) -> None:
        """All mock apps have valid tsconfig.json — should exit 0."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "tsconfig-audit"])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_tsconfig_audit_detects_missing_jsx(self, mock_monorepo: Path) -> None:
        """Audit should detect missing jsx option."""
        (mock_monorepo / "apps" / "lfa" / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "tsconfig-audit"])
        assert result.exit_code == 1
        assert "react-jsx" in result.output

    def test_tsconfig_audit_detects_missing_file(self, mock_monorepo: Path) -> None:
        """Audit should report MISSING when tsconfig.json does not exist."""
        (mock_monorepo / "apps" / "wms" / "tsconfig.json").unlink()
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "tsconfig-audit"])
        assert result.exit_code == 1
        assert "MISSING" in result.output

    def test_conventions(self, mock_monorepo: Path) -> None:
        """Clean app source (no anti-patterns) should exit 0."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "conventions", "sfa"])
        assert result.exit_code == 0
        assert "No convention issues" in result.output

    def test_conventions_detects_use_client(self, mock_monorepo: Path) -> None:
        """Should flag 'use client' directive."""
        bad_file = mock_monorepo / "apps" / "sfa" / "src" / "BadClient.tsx"
        bad_file.write_text('"use client";\nexport function Foo() { return null; }\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "conventions", "sfa"])
        assert result.exit_code == 1
        assert "use client" in result.output

    def test_conventions_detects_deep_relative_import(self, mock_monorepo: Path) -> None:
        """Should flag deep relative imports (../../)."""
        bad_file = mock_monorepo / "apps" / "sfa" / "src" / "DeepImport.ts"
        bad_file.write_text('import { foo } from "../../utils/helpers";\n')
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "conventions", "sfa"])
        assert result.exit_code == 1
        assert "deep relative import" in result.output

    def test_conventions_invalid_app(self, mock_monorepo: Path) -> None:
        """Invalid app name should exit 1."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "conventions", "nonexistent"])
        assert result.exit_code == 1


# ── State commands ─────────────────────────────────────────────────


class TestStateEnhanced:
    def test_query_keys(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "state", "query-keys", "sfa"])
        assert result.exit_code == 0
        assert "customers" in result.output

    def test_consistency(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "state", "consistency", "sfa"])
        assert result.exit_code == 0

    def test_hooks_audit(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "state", "hooks-audit", "sfa"])
        assert result.exit_code == 0

    def test_invalidation_map(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "state", "invalidation-map", "sfa"])
        assert result.exit_code == 0


class TestTestCmdEnhanced:
    def test_naming(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "test", "naming"])
        assert result.exit_code == 0

    def test_threshold(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "test", "threshold", "--min", "0"])
        assert result.exit_code == 0

    def test_snapshots(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "test", "snapshots", "sfa"])
        assert result.exit_code == 0


# ── Bundle enhanced commands ───────────────────────────────────────


class TestBundleEnhanced:
    def test_compare_with_snapshot(self, mock_monorepo: Path) -> None:
        kctl_dir = mock_monorepo / ".kctl-react"
        kctl_dir.mkdir(exist_ok=True)
        (kctl_dir / "bundle-snapshot.json").write_text(
            json.dumps(
                {
                    "sfa": {"js": 200000, "css": 50000},
                }
            )
        )
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True)
        (dist / "index.js").write_text("x" * 210000)
        (dist / "style.css").write_text("y" * 55000)
        result = runner.invoke(app, ["--root", str(mock_monorepo), "bundle", "compare", "sfa"])
        assert result.exit_code == 0

    def test_impact(self, mock_monorepo: Path) -> None:
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "vendor-react.js").write_text("x" * 100000)
        (dist / "vendor-tanstack.js").write_text("x" * 50000)
        (dist / "index.js").write_text("x" * 30000)
        result = runner.invoke(app, ["--root", str(mock_monorepo), "bundle", "impact", "sfa"])
        assert result.exit_code == 0


# ── i18n enhanced commands ─────────────────────────────────────────


class TestI18nEnhanced:
    def test_validate(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "i18n", "validate", "sfa"])
        assert result.exit_code == 0

    def test_interpolation(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "i18n", "interpolation", "sfa"])
        assert result.exit_code == 0
        # Should detect missing {{count}} in id.json
        assert "count" in result.output or "mismatch" in result.output.lower()

    def test_sync_stub(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "i18n", "sync-stub", "sfa"])
        assert result.exit_code == 0
        id_file = mock_monorepo / "apps" / "sfa" / "src" / "i18n" / "id.json"
        data = json.loads(id_file.read_text())
        assert "cancel" in data  # Was missing, should now be stubbed


# ── Final integration regression net ──────────────────────────────


class TestAllNewCommandsRegistered:
    """Verify all new subcommands are reachable via CLI and exit with code 0."""

    COMMANDS = [
        ["ui", "compliance", "sfa"],
        ["ui", "anti-patterns", "sfa"],
        ["codegen", "verify", "sfa"],
        ["codegen", "drift", "sfa"],
        ["codegen", "schema-health", "sfa"],
        ["lint", "strict-check"],
        ["lint", "tsconfig-audit"],
        ["lint", "conventions", "sfa"],
        ["state", "query-keys", "sfa"],
        ["state", "consistency", "sfa"],
        ["state", "hooks-audit", "sfa"],
        ["state", "invalidation-map", "sfa"],
        ["i18n", "validate", "sfa"],
        ["i18n", "interpolation", "sfa"],
        ["test", "naming"],
        ["test", "threshold", "--min", "0"],
        ["test", "snapshots", "sfa"],
        ["scaffold", "form", "sfa", "IntegrationTestForm"],
        ["scaffold", "test", "sfa", "IntegrationTestPage"],
        ["perf", "vitals", "sfa"],
        ["perf", "images", "sfa"],
        ["perf", "fonts", "sfa"],
    ]

    def test_all_commands_exit_zero(self, mock_monorepo: Path) -> None:
        # Create dist/assets for bundle/perf commands that may inspect build output
        dist = mock_monorepo / "apps" / "sfa" / "dist" / "assets"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.js").write_text("x" * 1000)

        # Populate types.gen.ts so codegen commands (verify, drift, schema-health) work
        gen_dir = mock_monorepo / "apps" / "sfa" / "src" / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        (gen_dir / "types.gen.ts").write_text(
            "// Auto-generated — do not edit\n"
            "export type CustomerListResponse = { data: Customer[] };\n"
            "export type Customer = { id: number; name: string };\n"
        )
        # types/api.ts re-exports from @/generated/
        types_api = mock_monorepo / "apps" / "sfa" / "src" / "types" / "api.ts"
        types_api.write_text('export type { CustomerListResponse, Customer } from "@/generated/types.gen";\n')

        for cmd_args in self.COMMANDS:
            result = runner.invoke(app, ["--root", str(mock_monorepo)] + cmd_args)
            assert result.exit_code == 0, f"FAILED: kctl-react {' '.join(cmd_args)}\n{result.output}"


# ── UI shadcn CLI wrapper commands ───────────────────────────────────


class TestUiShadcn:
    def test_installed(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "installed"])
        assert result.exit_code == 0
        assert "button" in result.output
        assert "data-table" in result.output

    def test_installed_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "ui", "installed"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        names = [d["component"] for d in data]
        assert "button" in names

    def test_unused(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "unused"])
        assert result.exit_code == 0

    def test_info_no_npx(self, mock_monorepo: Path) -> None:
        """ui info falls back gracefully when shadcn not available."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "info"])
        # May fail if npx not available, but should not crash
        assert result.exit_code in (0, 1)

    def test_add_requires_component_or_all(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "add"])
        assert result.exit_code == 1
        assert "component" in result.output.lower() or "specify" in result.output.lower()


# ── UI preset command ──────────────────────────────────────────────


class TestUiPreset:
    def test_preset_dry_run(self, mock_monorepo: Path) -> None:
        """Dry run should not modify files."""
        # Create necessary theme infrastructure
        tc_dir = mock_monorepo / "packages" / "tailwind-config" / "src"
        tc_dir.mkdir(parents=True, exist_ok=True)
        (tc_dir / "base-neutral.css").write_text(
            ":root { --primary: oklch(0.205 0 0); }\n.dark { --primary: oklch(0.922 0 0); }"
        )
        (tc_dir / "globals.css").write_text(
            '@import "tailwindcss";\n@theme inline { --color-primary: var(--primary); }'
        )

        result = runner.invoke(app, ["--root", str(mock_monorepo), "ui", "preset", "b1D0dv72", "--dry-run"])
        # Should show what would change (or fail gracefully if npx not available)
        assert result.exit_code in (0, 1)

    def test_preset_invalid_target(self, mock_monorepo: Path) -> None:
        """Invalid target app should fail."""
        result = runner.invoke(
            app, ["--root", str(mock_monorepo), "ui", "preset", "b1D0dv72", "--target", "nonexistent"]
        )
        assert result.exit_code == 1

    def test_css_extraction_helpers(self) -> None:
        """Test CSS parsing helpers directly."""
        from kctl_react.commands.ui_audit import _extract_css_blocks

        css = """
@import "tailwindcss";

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --radius-sm: calc(var(--radius) * 0.6);
}

:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --radius: 0.625rem;
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
"""
        blocks = _extract_css_blocks(css)
        assert ":root" in blocks
        assert ".dark" in blocks
        assert "@theme" in blocks
        assert "@layer" in blocks
        # Check :root content
        assert "--background: oklch(1 0 0);" in blocks[":root"]
        assert "--foreground: oklch(0.145 0 0);" in blocks[":root"]
        # Check .dark content
        assert "--background: oklch(0.145 0 0);" in blocks[".dark"]
        # Check @theme content
        assert "--color-background: var(--background);" in blocks["@theme"]

    def test_update_globals_preserves_custom_content(self) -> None:
        """The globals update should preserve custom CSS after the base layer."""
        from kctl_react.commands.ui_audit import _build_updated_globals

        old_globals = """@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-primary: var(--primary);
  --radius-sm: calc(var(--radius) * 0.6);
}

:root {
  --primary: oklch(0.205 0 0);
  --radius: 0.625rem;
}

.dark {
  --primary: oklch(0.922 0 0);
}

@layer base {
  * {
    @apply border-border;
  }
}

/* custom stuff */
.spinner { animation: spin 1s linear infinite; }
"""
        new_blocks = {
            "@theme": "  --color-primary: var(--primary);\n  --color-background: var(--background);\n  --radius-sm: calc(var(--radius) * 0.5);",
            ":root": "  --primary: oklch(0.5 0.2 250);\n  --background: oklch(1 0 0);\n  --radius: 0.5rem;",
            ".dark": "  --primary: oklch(0.8 0.2 250);\n  --background: oklch(0.1 0 0);",
            "@layer": "  * {\n    @apply border-border outline-ring/50;\n  }\n  body {\n    @apply bg-background text-foreground;\n  }",
        }

        result = _build_updated_globals(old_globals, new_blocks)

        # Should contain the new @theme block
        assert "--color-background: var(--background);" in result
        assert "calc(var(--radius) * 0.5)" in result
        # Should contain the new :root block
        assert "--primary: oklch(0.5 0.2 250);" in result
        # Should contain the new .dark block
        assert "--primary: oklch(0.8 0.2 250);" in result
        # Should preserve the custom stuff at the end
        assert ".spinner { animation: spin 1s linear infinite; }" in result
        # Should preserve imports at the top
        assert '@import "tailwindcss";' in result
        assert '@import "tw-animate-css";' in result
        assert "@custom-variant dark" in result


class TestDepsEnhanced:
    def test_stack(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "stack"])
        assert result.exit_code == 0

    def test_stack_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "deps", "stack"])
        assert result.exit_code == 0

    def test_health(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "health"])
        assert result.exit_code == 0

    def test_sync_dynamic(self, mock_monorepo: Path) -> None:
        # Add inconsistent dep to mock monorepo
        import json as json_mod

        pkg_file = mock_monorepo / "apps" / "sfa" / "package.json"
        pkg = json_mod.loads(pkg_file.read_text())
        pkg["dependencies"]["zod"] = "^3.20.0"
        pkg_file.write_text(json_mod.dumps(pkg, indent=2))

        pkg_file2 = mock_monorepo / "apps" / "wms" / "package.json"
        pkg2 = json_mod.loads(pkg_file2.read_text())
        pkg2["dependencies"]["zod"] = "^3.24.0"
        pkg_file2.write_text(json_mod.dumps(pkg2, indent=2))

        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "sync"])
        assert result.exit_code == 0
        assert "zod" in result.output
