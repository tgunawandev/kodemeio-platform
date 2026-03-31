"""Smoke tests -- run against a live Hetzner Cloud API.

Skip if no profile is configured or API is unreachable.
Run with: pytest tests/test_smoke.py -v --tb=short -m smoke

Integration tests are skipped by default. Enable with:
    pytest tests/test_smoke.py -v --tb=short -m integration
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

PROFILE = os.environ.get("KCTL_TEST_PROFILE", "default")


def _has_valid_token() -> bool:
    """Check whether a Hetzner API token is configured in the profile."""
    config_path = Path.home() / ".config" / "kodemeio" / "config.yaml"
    if not config_path.exists():
        return False
    try:
        cfg = yaml.safe_load(config_path.read_text()) or {}
        token = cfg.get("profiles", {}).get(PROFILE, {}).get("hetzner", {}).get("token", "")
        return bool(token)
    except Exception:
        return False


_TOKEN_AVAILABLE = _has_valid_token()
_skip_no_token = pytest.mark.skipif(
    not _TOKEN_AVAILABLE,
    reason=f"No valid Hetzner API token configured for profile '{PROFILE}'",
)


def _run(cmd: str, json_mode: bool = True, timeout: int = 30) -> tuple:
    """Run kctl-hz and return (data, returncode)."""
    args = ["kctl-hz", "-p", PROFILE]
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


@pytest.mark.smoke
@pytest.mark.integration
@_skip_no_token
class TestCoreCommands:
    """Core commands that must always work with valid API token."""

    def test_health_check(self):
        data, rc = _run("health check")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_servers_list(self):
        data, rc = _run("servers list")
        assert rc == 0
        assert isinstance(data, list)

    def test_volumes_list(self):
        data, rc = _run("volumes list")
        assert rc == 0
        assert isinstance(data, list)

    def test_firewalls_list(self):
        data, rc = _run("firewalls list")
        assert rc == 0
        assert isinstance(data, list)

    def test_networks_list(self):
        data, rc = _run("networks list")
        assert rc == 0
        assert isinstance(data, list)

    def test_ssh_keys_list(self):
        data, rc = _run("ssh-keys list")
        assert rc == 0
        assert isinstance(data, list)

    def test_images_list(self):
        data, rc = _run("images list")
        assert rc == 0
        assert isinstance(data, list)

    def test_locations_list(self):
        data, rc = _run("locations list")
        assert rc == 0
        assert isinstance(data, list)

    def test_server_types_list(self):
        data, rc = _run("server-types list")
        assert rc == 0
        assert isinstance(data, list)


@pytest.mark.smoke
@pytest.mark.integration
@_skip_no_token
class TestOutputFormats:
    """Verify CSV output contains no Rich markup artifacts."""

    def test_csv_no_markup(self):
        output, rc = _run("servers list --format csv", json_mode=False)
        assert rc == 0
        assert "[green]" not in output
        assert "[bold]" not in output

    def test_json_valid(self):
        data, rc = _run("servers list")
        assert rc == 0
        assert isinstance(data, list)


@pytest.mark.smoke
@pytest.mark.integration
@_skip_no_token
class TestReferenceData:
    """Reference data commands should always work."""

    def test_costs_estimate(self):
        data, rc = _run("costs estimate")
        assert rc == 0
        assert isinstance(data, (dict, list))

    def test_status_show(self):
        data, rc = _run("status show")
        assert rc == 0
        assert isinstance(data, (dict, list))


@pytest.mark.smoke
@pytest.mark.integration
@_skip_no_token
class TestGracefulDegradation:
    """Commands should not traceback even if resources are missing."""

    def test_dns_zones_no_crash(self):
        output, rc = _run("dns zones", json_mode=False)
        assert "Traceback" not in output

    def test_s3_buckets_no_crash(self):
        output, rc = _run("s3 buckets", json_mode=False)
        assert "Traceback" not in output
