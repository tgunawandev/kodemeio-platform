"""Smoke tests -- run against a live Odoo instance.

Skip if no profile is configured or Odoo is unreachable.
Run with: pytest tests/test_smoke.py -v --tb=short
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

PROFILE = os.environ.get("KCTL_TEST_PROFILE", "odoo_full")


def _run(cmd: str, json_mode: bool = True, timeout: int = 30) -> tuple:
    """Run kctl-odoo and return (data, returncode)."""
    args = ["kctl-odoo", "-p", PROFILE]
    if json_mode:
        args.append("--json")
    args.extend(cmd.split())
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if json_mode and result.returncode == 0:
        try:
            return json.loads(result.stdout), result.returncode
        except json.JSONDecodeError:
            return result.stdout, result.returncode
    return result.stdout, result.returncode


@pytest.fixture(scope="session", autouse=True)
def check_connectivity():
    """Skip all smoke tests if Odoo is unreachable."""
    try:
        data, rc = _run("health check")
        if rc != 0:
            pytest.skip(f"Odoo unreachable on profile {PROFILE}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("kctl-odoo not installed or Odoo unreachable")


@pytest.mark.smoke
class TestCoreCommands:
    """Core commands that must always work on a running Odoo instance."""

    def test_health_check(self):
        data, rc = _run("health check")
        assert rc == 0
        assert isinstance(data, dict)
        assert "healthy" in data or "version" in data

    def test_dashboard_info(self):
        data, rc = _run("dashboard info")
        assert rc == 0
        assert isinstance(data, dict)

    def test_modules_check_sale(self):
        data, rc = _run("modules check sale")
        assert rc == 0
        assert isinstance(data, dict)
        assert data.get("installed") is True

    def test_users_list(self):
        data, rc = _run("users list")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_databases_list(self):
        data, rc = _run("databases list")
        assert rc == 0
        assert isinstance(data, (dict, list))


@pytest.mark.smoke
class TestOutputFormats:
    """Verify CSV and JSON output contain no Rich markup artifacts."""

    def test_csv_no_markup(self):
        output, rc = _run("modules list --state installed", json_mode=False)
        assert rc == 0
        assert "[green]" not in output
        assert "[bold]" not in output
        assert "[red]" not in output

    def test_json_valid_structure(self):
        data, rc = _run("security security-audit", timeout=60)
        assert rc == 0
        assert isinstance(data, (dict, list))


@pytest.mark.smoke
class TestNewFeatures:
    """Verify newer commands return structured data."""

    def test_mail_status(self):
        data, rc = _run("mail status")
        assert rc == 0
        assert isinstance(data, dict)

    def test_daily_digest(self):
        data, rc = _run("biz daily-digest")
        assert rc == 0
        assert isinstance(data, dict)

    def test_storage_overview(self):
        data, rc = _run("storage overview")
        assert rc == 0
        assert isinstance(data, dict)

    def test_check_config(self):
        data, rc = _run("troubleshoot check-config")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_version_info(self):
        data, rc = _run("troubleshoot version-info")
        assert rc == 0
        assert isinstance(data, dict)

    def test_configure_audit(self):
        data, rc = _run("configure audit")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_monthly_close(self):
        data, rc = _run("maintenance monthly-close")
        # May return non-zero if blocking issues found — that's OK
        assert rc in (0, 1)

    def test_low_stock(self):
        data, rc = _run("biz low-stock --threshold 10")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_queue_throughput(self):
        data, rc = _run("performance queue-throughput")
        assert rc == 0
        assert isinstance(data, dict)


@pytest.mark.smoke
class TestGracefulDegradation:
    """Commands that may hit missing modules should not traceback."""

    def test_oauth_list_no_crash(self):
        output, rc = _run("integration oauth-list", json_mode=False)
        assert "Traceback" not in output

    def test_fastapi_health(self):
        output, rc = _run("fastapi health tpm", json_mode=False)
        assert "Traceback" not in output
