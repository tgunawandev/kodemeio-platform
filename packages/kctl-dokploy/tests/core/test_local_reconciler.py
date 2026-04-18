"""Unit tests for LocalReconciler.

All external calls (Cloudflare, Dokploy API, filesystem) are mocked.
Tests only exercise pure logic + wiring.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_dokploy.core.local_reconciler import (
    KctlCfDnsAdapter,
    LocalDokployAdapter,
    LocalReconciler,
)
from kctl_dokploy.core.manifest import load_and_resolve


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubDnsAdapter:
    """In-memory DNS: name -> content."""

    records: dict[str, str]

    def get(self, zone: str, name: str) -> str | None:
        return self.records.get(name)

    def update(self, zone: str, name: str, content: str) -> None:
        self.records[name] = content


@dataclass
class _StubDokployDomains:
    """In-memory domain store: compose_id -> list[dict]."""

    store: dict[str, list[dict]] = field(default_factory=dict)
    created: list[dict] = field(default_factory=list)

    def list_for_compose(self, compose_id: str) -> list[dict]:
        return list(self.store.get(compose_id, []))

    def create(self, *, compose_id: str, **spec: object) -> None:
        self.store.setdefault(compose_id, []).append({"composeId": compose_id, **spec})
        self.created.append({"composeId": compose_id, **spec})

    def update(self, domain_id: str, **spec: object) -> None:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Task 13: reconcile_dns
# ---------------------------------------------------------------------------


def test_reconcile_dns_no_drift_is_noop() -> None:
    dns = _StubDnsAdapter(records={"*.local.kodeme.io": "192.168.1.5", "local.kodeme.io": "192.168.1.5"})
    r = LocalReconciler(
        dns=dns,
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_dns()
    assert result.changed is False
    assert "*.local.kodeme.io" in result.inspected
    assert dns.records["*.local.kodeme.io"] == "192.168.1.5"


def test_reconcile_dns_drift_triggers_update() -> None:
    dns = _StubDnsAdapter(records={"*.local.kodeme.io": "192.168.1.10", "local.kodeme.io": "192.168.1.10"})
    r = LocalReconciler(
        dns=dns,
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_dns()
    assert result.changed is True
    assert dns.records["*.local.kodeme.io"] == "192.168.1.5"
    assert dns.records["local.kodeme.io"] == "192.168.1.5"


def test_reconcile_dns_raises_when_lan_ip_is_public() -> None:
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("8.8.8.8"),
        zone="kodeme.io",
    )
    with pytest.raises(ValueError, match="not RFC1918"):
        r.reconcile_dns()


# ---------------------------------------------------------------------------
# Task 14: reconcile_domain
# ---------------------------------------------------------------------------


def test_reconcile_domain_creates_missing_domain() -> None:
    domains = _StubDokployDomains()
    dokploy = MagicMock()
    dokploy.domains = domains
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=dokploy,
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_domain(
        compose_id="cmp_abc",
        host="dbgate.local.kodeme.io",
        port=3000,
        service="dbgate",
    )
    assert result.changed is True
    assert domains.created == [
        {
            "composeId": "cmp_abc",
            "host": "dbgate.local.kodeme.io",
            "port": 3000,
            "service_name": "dbgate",
            "https": True,
            "cert_type": "none",
        }
    ]


def test_reconcile_domain_noop_when_exact_match_exists() -> None:
    domains = _StubDokployDomains(
        store={
            "cmp_abc": [
                {
                    "composeId": "cmp_abc",
                    "host": "dbgate.local.kodeme.io",
                    "port": 3000,
                    "service_name": "dbgate",
                    "https": True,
                    "cert_type": "none",
                }
            ]
        }
    )
    dokploy = MagicMock()
    dokploy.domains = domains
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=dokploy,
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_domain(
        compose_id="cmp_abc",
        host="dbgate.local.kodeme.io",
        port=3000,
        service="dbgate",
    )
    assert result.changed is False
    assert domains.created == []


def test_reconcile_domain_rejects_non_local_host() -> None:
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    with pytest.raises(ValueError, match="must end with .local.kodeme.io"):
        r.reconcile_domain(
            compose_id="cmp_abc",
            host="dbgate.kodeme.io",  # missing ".local"
            port=3000,
            service="dbgate",
        )


# ---------------------------------------------------------------------------
# Task 15: apply (end-to-end manifest)
# ---------------------------------------------------------------------------


def _write_dbgate_manifest(tmp_path: Path) -> Path:
    """Write a self-contained local manifest (no `extends`) for testing."""
    p = tmp_path / "kod-infra-dbgate.yaml"
    p.write_text(
        """
kind: instance
project: application
environment: local
server: vbox-ubuntu-server
instance:
  name: kod-infra-dbgate
  description: DBGate
source:
  type: github
  owner: tgunawandev
  repo: kodemeio-dbgate
  branch: main
  compose_path: ./docker-compose.prod.yml
domain:
  host: dbgate.local.kodeme.io
  port: 3000
  service: dbgate
  https: true
env_file: .env.kod-infra-dbgate
""".strip()
    )
    # Create the referenced env file so load_and_resolve can resolve its path.
    (tmp_path / ".env.kod-infra-dbgate").write_text("FOO=bar\n")
    return p


def test_apply_refuses_non_local_environment(tmp_path: Path) -> None:
    p = tmp_path / "prod.yaml"
    p.write_text(
        """
kind: instance
project: application
environment: production
instance:
  name: foo
domain:
  host: foo.local.kodeme.io
  port: 80
  service: foo
""".strip()
    )
    manifest = load_and_resolve(p)
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    with pytest.raises(ValueError, match="refuses non-local"):
        r.apply(manifest)


def test_apply_dispatches_dns_compose_env_and_domain(tmp_path: Path) -> None:
    manifest_path = _write_dbgate_manifest(tmp_path)
    manifest = load_and_resolve(manifest_path)

    dns = _StubDnsAdapter(records={"*.local.kodeme.io": "192.168.1.5", "local.kodeme.io": "192.168.1.5"})
    domains = _StubDokployDomains()
    dokploy = MagicMock()
    dokploy.domains = domains
    # ensure_compose + push_env return reconcile-style dicts.
    dokploy.ensure_compose.return_value = {"changed": True, "compose_id": "cmp_dbgate"}
    dokploy.push_env.return_value = {"changed": False}

    r = LocalReconciler(
        dns=dns,
        dokploy=dokploy,
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    outcome = r.apply(manifest)

    assert dokploy.ensure_compose.call_count == 1
    assert dokploy.push_env.call_count == 1
    # Domain was created (none existed before)
    assert len(domains.created) == 1
    assert domains.created[0]["host"] == "dbgate.local.kodeme.io"
    assert domains.created[0]["cert_type"] == "none"
    # Overall changed because compose + domain changed
    assert outcome.changed is True


# ---------------------------------------------------------------------------
# Task 16: KctlCfDnsAdapter (shells out to `kctl-cf`)
# ---------------------------------------------------------------------------


def test_kctlcf_adapter_get_returns_content() -> None:
    # Simulate `kctl-cf ... records list` returning a JSON list containing our record.
    fake_proc = MagicMock(
        returncode=0,
        stdout=_json.dumps([{"name": "*.local.kodeme.io", "content": "192.168.1.5", "id": "r1"}]),
        stderr="",
    )
    with patch("kctl_dokploy.core.local_reconciler.subprocess.run", return_value=fake_proc):
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        assert adapter.get("kodeme.io", "*.local.kodeme.io") == "192.168.1.5"


def test_kctlcf_adapter_get_returns_none_when_absent() -> None:
    fake_proc = MagicMock(returncode=1, stdout="", stderr="Record not found")
    with patch("kctl_dokploy.core.local_reconciler.subprocess.run", return_value=fake_proc):
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        assert adapter.get("kodeme.io", "*.local.kodeme.io") is None


def test_kctlcf_adapter_update_invokes_kctl_cf() -> None:
    # `get` is called first to look up the record id, then `update` with that id.
    list_proc = MagicMock(
        returncode=0,
        stdout=_json.dumps([{"name": "*.local.kodeme.io", "content": "1.1.1.1", "id": "rec_123"}]),
        stderr="",
    )
    update_proc = MagicMock(returncode=0, stdout="OK", stderr="")
    with patch(
        "kctl_dokploy.core.local_reconciler.subprocess.run",
        side_effect=[list_proc, update_proc],
    ) as run_mock:
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        adapter.update("kodeme.io", "*.local.kodeme.io", "192.168.1.6")

        # Second call is the update; verify CLI shape.
        last_args = run_mock.call_args_list[-1].args[0]
        assert last_args[:3] == ["kctl-cf", "-p", "kodemeio"]
        assert "records" in last_args
        assert "update" in last_args
        assert "--content" in last_args and "192.168.1.6" in last_args


# ---------------------------------------------------------------------------
# Task 17: LocalDokployAdapter delegates to deploy_ops
# ---------------------------------------------------------------------------


def test_local_dokploy_adapter_delegates_to_deploy_ops(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n")

    mock_client = MagicMock()
    with patch("kctl_dokploy.core.local_reconciler.deploy_ops") as ops:
        ops.ensure_project_and_env.return_value = {"environment_id": "env_x"}
        ops.ensure_compose_service.return_value = {"changed": True, "compose_id": "cmp_x"}
        ops.push_env_file.return_value = {"changed": False, "count": 1}

        adapter = LocalDokployAdapter(client=mock_client)

        manifest = MagicMock(
            project="application",
            environment="local",
            server="vbox-ubuntu-server",
        )
        result = adapter.ensure_compose(manifest)
        assert result == {"changed": True, "compose_id": "cmp_x"}
        ops.ensure_project_and_env.assert_called_once()
        ops.ensure_compose_service.assert_called_once()

        env_result = adapter.push_env("cmp_x", env_file)
        assert env_result == {"changed": False, "count": 1}
        ops.push_env_file.assert_called_once_with(mock_client, "cmp_x", env_file, force=True)
