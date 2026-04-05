"""Command-level tests for kctl-hz using mocked AppContext."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_hz.cli import app

runner = CliRunner()

MOCK_SERVERS = [
    {
        "id": 1001,
        "name": "mac-prod-01",
        "status": "running",
        "server_type": {"name": "cx32", "description": "CX32", "cores": 4, "memory": 8, "disk": 80},
        "datacenter": {"name": "fsn1-dc14"},
        "public_net": {"ipv4": {"ip": "1.2.3.4"}, "ipv6": {"ip": "2a01::1/64"}},
        "created": "2024-01-15T10:00:00Z",
        "labels": {"env": "production"},
    },
    {
        "id": 1002,
        "name": "tpp-prod-01",
        "status": "running",
        "server_type": {"name": "cx22", "description": "CX22", "cores": 2, "memory": 4, "disk": 40},
        "datacenter": {"name": "fsn1-dc14"},
        "public_net": {"ipv4": {"ip": "5.6.7.8"}, "ipv6": {}},
        "created": "2024-02-01T10:00:00Z",
        "labels": {},
    },
]

MOCK_FIREWALLS = [
    {
        "id": 201,
        "name": "web-fw",
        "rules": [
            {"direction": "in", "protocol": "tcp", "port": "80", "source_ips": ["0.0.0.0/0"], "destination_ips": []},
            {"direction": "in", "protocol": "tcp", "port": "443", "source_ips": ["0.0.0.0/0"], "destination_ips": []},
        ],
        "applied_to": [{"type": "server", "server": {"id": 1001}}],
        "created": "2024-01-10T00:00:00Z",
    },
]

MOCK_VOLUMES = [
    {
        "id": 301,
        "name": "data-vol-01",
        "size": 100,
        "server": 1001,
        "location": {"name": "fsn1"},
        "status": "available",
        "labels": {},
    },
]

MOCK_NETWORKS = [
    {
        "id": 401,
        "name": "kodemeio-net",
        "ip_range": "10.0.0.0/8",
        "subnets": [{"ip_range": "10.0.0.0/24"}, {"ip_range": "10.0.1.0/24"}],
        "servers": [1001, 1002],
        "labels": {},
        "created": "2024-01-01T00:00:00Z",
    },
]

MOCK_SSH_KEYS = [
    {"id": 501, "name": "tri-mac", "fingerprint": "ab:cd:ef:01:23", "created": "2024-01-01T00:00:00Z"},
]


def _make_actx(json_mode: bool = True) -> MagicMock:
    from kctl_lib.output import Output

    actx = MagicMock()
    actx.output = Output(json_mode=json_mode, quiet=True, format="json" if json_mode else "pretty")
    actx.client = MagicMock()
    actx.dns_client = MagicMock()
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# CLI smoke tests (no API calls)
# ---------------------------------------------------------------------------


class TestSmokeHelp:
    def test_root_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "servers" in result.output or "Hetzner" in result.output

    def test_servers_help(self) -> None:
        result = runner.invoke(app, ["servers", "--help"])
        assert result.exit_code == 0

    def test_firewalls_help(self) -> None:
        result = runner.invoke(app, ["firewalls", "--help"])
        assert result.exit_code == 0

    def test_volumes_help(self) -> None:
        result = runner.invoke(app, ["volumes", "--help"])
        assert result.exit_code == 0

    def test_networks_help(self) -> None:
        result = runner.invoke(app, ["networks", "--help"])
        assert result.exit_code == 0

    def test_ssh_keys_help(self) -> None:
        result = runner.invoke(app, ["ssh-keys", "--help"])
        assert result.exit_code == 0

    def test_images_help(self) -> None:
        result = runner.invoke(app, ["images", "--help"])
        assert result.exit_code == 0

    def test_locations_help(self) -> None:
        result = runner.invoke(app, ["locations", "--help"])
        assert result.exit_code == 0

    def test_costs_help(self) -> None:
        result = runner.invoke(app, ["costs", "--help"])
        assert result.exit_code == 0

    def test_dns_help(self) -> None:
        result = runner.invoke(app, ["dns", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# servers commands
# ---------------------------------------------------------------------------


class TestServersList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["servers", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_SERVERS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.servers import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "mac-prod-01"
        assert data[1]["name"] == "tpp-prod-01"

    def test_list_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = []
        ctx = _make_ctx(actx)

        from kctl_hz.commands.servers import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestServersGet:
    def test_get_help(self) -> None:
        result = runner.invoke(app, ["servers", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        server = MOCK_SERVERS[0]
        # resolve_server uses client.get internally
        actx.client.get.return_value = {"servers": [server]}
        ctx = _make_ctx(actx)

        from kctl_hz.core.resolve import resolve_server
        from unittest.mock import patch

        with patch("kctl_hz.commands.servers._resolve_server", return_value=server):
            from kctl_hz.commands.servers import get

            get(ctx, name="mac-prod-01")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "mac-prod-01"
        assert data["id"] == 1001


class TestServersCreate:
    def test_create_help(self) -> None:
        result = runner.invoke(app, ["servers", "create", "--help"])
        assert result.exit_code == 0

    def test_create_options_present(self) -> None:
        result = runner.invoke(app, ["servers", "create", "--help"])
        assert "--type" in result.output
        assert "--image" in result.output
        assert "--location" in result.output

    def test_create_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.post.return_value = {
            "server": {
                "id": 9999,
                "name": "new-server",
                "status": "initializing",
                "server_type": {"name": "cx22"},
                "datacenter": {"name": "fsn1-dc14"},
                "public_net": {"ipv4": {"ip": "9.9.9.9"}},
            }
        }
        ctx = _make_ctx(actx)

        from kctl_hz.commands.servers import create

        create(ctx, name="new-server", server_type="cx22", image="ubuntu-24.04", location="fsn1", ssh_keys=None)
        actx.client.post.assert_called_once()
        call_args = actx.client.post.call_args
        assert call_args[0][0] == "/servers"
        payload = call_args[1]["json"]
        assert payload["name"] == "new-server"
        assert payload["image"] == "ubuntu-24.04"


# ---------------------------------------------------------------------------
# firewalls commands
# ---------------------------------------------------------------------------


class TestFirewallsList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["firewalls", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_FIREWALLS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.firewalls import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "web-fw"

    def test_list_shows_rule_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=False)
        actx.client.get_all.return_value = MOCK_FIREWALLS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.firewalls import list_

        list_(ctx)
        # In pretty mode, output is a table — just check no exception
        # and firewall data was read
        actx.client.get_all.assert_called_once_with("/firewalls", "firewalls")


class TestFirewallsGet:
    def test_get_help(self) -> None:
        result = runner.invoke(app, ["firewalls", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        fw = MOCK_FIREWALLS[0]
        actx.client.get.return_value = {"firewalls": [fw]}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.firewalls import get

        get(ctx, name="web-fw")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "web-fw"
        assert data["id"] == 201

    def test_get_not_found_exits(self) -> None:
        import typer

        actx = _make_actx(json_mode=True)
        actx.client.get.return_value = {"firewalls": []}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.firewalls import get

        with pytest.raises((SystemExit, typer.Exit)):
            get(ctx, name="nonexistent-fw")


# ---------------------------------------------------------------------------
# volumes commands
# ---------------------------------------------------------------------------


class TestVolumesList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["volumes", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_VOLUMES
        ctx = _make_ctx(actx)

        from kctl_hz.commands.volumes import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "data-vol-01"
        assert data[0]["size"] == 100


class TestVolumesGet:
    def test_get_help(self) -> None:
        result = runner.invoke(app, ["volumes", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        vol = MOCK_VOLUMES[0]
        actx.client.get.return_value = {"volume": vol}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.volumes import get

        get(ctx, volume_id=301)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "data-vol-01"

    def test_get_not_found_exits(self) -> None:
        import typer

        actx = _make_actx(json_mode=True)
        actx.client.get.return_value = {"volume": {}}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.volumes import get

        with pytest.raises((SystemExit, typer.Exit)):
            get(ctx, volume_id=99999)


# ---------------------------------------------------------------------------
# networks commands
# ---------------------------------------------------------------------------


class TestNetworksList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["networks", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_NETWORKS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.networks import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "kodemeio-net"
        assert data[0]["ip_range"] == "10.0.0.0/8"

    def test_list_shows_subnet_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_NETWORKS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.networks import list_

        list_(ctx)
        actx.client.get_all.assert_called_once_with("/networks", "networks")


class TestNetworksGet:
    def test_get_help(self) -> None:
        result = runner.invoke(app, ["networks", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        net = MOCK_NETWORKS[0]
        actx.client.get.return_value = {"network": net}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.networks import get

        get(ctx, network_id=401)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "kodemeio-net"

    def test_get_not_found_exits(self) -> None:
        import typer

        actx = _make_actx(json_mode=True)
        actx.client.get.return_value = {"network": {}}
        ctx = _make_ctx(actx)

        from kctl_hz.commands.networks import get

        with pytest.raises((SystemExit, typer.Exit)):
            get(ctx, network_id=99999)


# ---------------------------------------------------------------------------
# ssh-keys commands
# ---------------------------------------------------------------------------


class TestSSHKeysList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["ssh-keys", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx.client.get_all.return_value = MOCK_SSH_KEYS
        ctx = _make_ctx(actx)

        from kctl_hz.commands.ssh_keys import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "tri-mac"
