"""Tests for deployment preflight gates."""

from __future__ import annotations

from kctl_dokploy.core.preflight import GateResult, _gate_env_sync, run_preflight
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
    # With ssh_available=False and client=None, gates return fail/warn/pass depending on config
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


class TestGateEnvSync:
    def test_pass_when_no_env_file(self):
        m = DeployManifest()
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_fail_when_env_file_missing(self, tmp_path):
        m = DeployManifest(env_file=str(tmp_path / "nonexistent.env"))
        r = _gate_env_sync(m, None, False)
        assert r.status == "fail"
        assert "not found" in r.message

    def test_pass_when_env_file_exists(self, tmp_path):
        env_file = tmp_path / ".env.test"
        env_file.write_text("KEY=value\n")
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_fail_when_oidc_mode_but_empty_client_id(self, tmp_path):
        env_file = tmp_path / ".env.test"
        env_file.write_text("VITE_AUTH_MODE=oidc\nVITE_SFA_OIDC_CLIENT_ID=\nVITE_SFA_OIDC_REDIRECT_URI=\n")
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "fail"
        assert "OIDC" in r.message

    def test_pass_when_oidc_mode_with_credentials(self, tmp_path):
        env_file = tmp_path / ".env.test"
        env_file.write_text(
            "VITE_AUTH_MODE=oidc\n"
            "VITE_SFA_OIDC_CLIENT_ID=abc123\n"
            "VITE_SFA_OIDC_REDIRECT_URI=https://example.com/callback\n"
        )
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_pass_when_native_mode_empty_oidc(self, tmp_path):
        env_file = tmp_path / ".env.test"
        env_file.write_text("VITE_AUTH_MODE=native\nVITE_SFA_OIDC_CLIENT_ID=\n")
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"
