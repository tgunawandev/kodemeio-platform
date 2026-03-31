"""Smoke tests -- run against a live Cloudflare API.

Skip if no profile is configured or Cloudflare is unreachable.
Run with: pytest tests/test_smoke.py -v --tb=short
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

PROFILE = os.environ.get("KCTL_TEST_PROFILE", "kodemeio")


def _run(cmd: str, json_mode: bool = True, timeout: int = 30) -> tuple:
    """Run kctl-cf and return (data, returncode)."""
    args = ["kctl-cf", "-p", PROFILE]
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
    """Skip all smoke tests if Cloudflare is unreachable."""
    try:
        data, rc = _run("health check")
        if rc != 0:
            pytest.skip(f"Cloudflare unreachable on profile {PROFILE}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("kctl-cf not installed or Cloudflare unreachable")


@pytest.mark.smoke
class TestCoreCommands:
    """Core commands that must always work with a valid API token."""

    def test_health_check(self):
        data, rc = _run("health check")
        assert rc == 0
        assert isinstance(data, dict)
        assert "healthy" in data

    def test_zones_list(self):
        data, rc = _run("zones list")
        assert rc == 0
        assert isinstance(data, list)

    def test_config_show(self):
        output, rc = _run("config show", json_mode=False)
        assert rc == 0
        assert "Traceback" not in output


@pytest.mark.smoke
class TestOutputFormats:
    """Verify CSV and JSON output contain no Rich markup artifacts."""

    def test_csv_no_markup(self):
        output, rc = _run("zones list --format csv", json_mode=False)
        assert rc == 0
        assert "[green]" not in output
        assert "[bold]" not in output

    def test_json_valid_structure(self):
        data, rc = _run("zones list")
        assert rc == 0
        assert isinstance(data, list)


@pytest.mark.smoke
class TestDnsCommands:
    """DNS record commands."""

    def test_records_list(self):
        data, rc = _run("records list")
        assert rc == 0
        assert isinstance(data, list)


@pytest.mark.smoke
class TestGracefulDegradation:
    """Commands that may fail should not traceback."""

    def test_tunnels_list_no_crash(self):
        output, rc = _run("tunnels list", json_mode=False)
        assert "Traceback" not in output

    def test_workers_list_no_crash(self):
        output, rc = _run("workers list", json_mode=False)
        assert "Traceback" not in output

    def test_r2_list_no_crash(self):
        output, rc = _run("r2 list", json_mode=False)
        assert "Traceback" not in output
