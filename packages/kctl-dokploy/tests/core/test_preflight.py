"""Tests for deployment preflight gates."""

from __future__ import annotations

from kctl_dokploy.core.preflight import GateResult, run_preflight
from kctl_dokploy.core.manifest import DeployManifest


def test_gate_result_pass():
    r = GateResult(gate="test", status="pass", message="OK")
    assert r.passed
    assert not r.failed


def test_gate_result_fail():
    r = GateResult(gate="test", status="fail", message="Bad")
    assert not r.passed
    assert r.failed


def test_gate_result_warn():
    r = GateResult(gate="test", status="warn", message="Maybe")
    assert r.passed  # warn is not a failure
    assert not r.failed


def test_run_preflight_returns_results():
    """run_preflight returns a list of GateResults."""
    manifest = DeployManifest(
        server="test-server",
        project="test",
        environment="production",
    )
    # With no real connections, all gates should fail or be skipped
    results = run_preflight(manifest, client=None, ssh_available=False)
    assert isinstance(results, list)
    assert len(results) == 10
    assert all(isinstance(r, GateResult) for r in results)


def test_run_preflight_has_all_gates():
    """run_preflight checks all 10 gates."""
    manifest = DeployManifest(server="x", project="x")
    results = run_preflight(manifest, client=None, ssh_available=False)
    gate_names = {r.gate for r in results}
    expected = {
        "server_connectivity",
        "firewall",
        "dns",
        "image_pull",
        "database",
        "compose_assignment",
        "env_sync",
        "source_config",
        "network",
        "ssl",
    }
    assert gate_names == expected
