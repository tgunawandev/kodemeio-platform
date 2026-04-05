"""Extended command-level tests for kctl-cf: zones, records, waf, cache."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import click
import pytest
from typer.testing import CliRunner

from kctl_cf.cli import app
from tests.conftest import _make_actx, _make_ctx

runner = CliRunner()

MOCK_ZONES = [
    {
        "id": "zone_abc",
        "name": "kodeme.io",
        "status": "active",
        "plan": {"name": "Free"},
        "name_servers": ["ns1.cloudflare.com", "ns2.cloudflare.com"],
    },
    {
        "id": "zone_def",
        "name": "mandiriagro.com",
        "status": "active",
        "plan": {"name": "Pro"},
        "name_servers": ["ns1.cloudflare.com"],
    },
]

MOCK_DNS_RECORDS = [
    {"id": "rec_1", "type": "A", "name": "kodeme.io", "content": "1.2.3.4", "ttl": 1, "proxied": True},
    {"id": "rec_2", "type": "CNAME", "name": "www.kodeme.io", "content": "kodeme.io", "ttl": 1, "proxied": True},
    {"id": "rec_3", "type": "MX", "name": "kodeme.io", "content": "mail.kodeme.io", "ttl": 300, "proxied": False},
]

MOCK_WAF_RULES = [
    {
        "id": "rule_a1b2c3d4e5f6",
        "action": "block",
        "filter": {"expression": '(ip.geoip.country eq "XX")'},
        "priority": 1,
        "paused": False,
        "description": "Block bad country",
    },
]

MOCK_TUNNELS = [
    {
        "id": "tun_abc",
        "name": "main-tunnel",
        "status": "healthy",
        "connections": [{"id": "conn_1", "region": "eu"}],
    },
]


# ---------------------------------------------------------------------------
# Additional zones tests
# ---------------------------------------------------------------------------


class TestZonesExtended:
    def test_zones_list_help(self) -> None:
        result = runner.invoke(app, ["zones", "list", "--help"])
        assert result.exit_code == 0

    def test_zones_get_help(self) -> None:
        result = runner.invoke(app, ["zones", "get", "--help"])
        assert result.exit_code == 0

    def test_zones_create_help(self) -> None:
        result = runner.invoke(app, ["zones", "create", "--help"])
        assert result.exit_code == 0

    def test_zones_purge_help(self) -> None:
        result = runner.invoke(app, ["zones", "purge-cache", "--help"])
        assert result.exit_code == 0

    def test_zones_get_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = MOCK_ZONES[0]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.zones import get

        get(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "kodeme.io"
        assert data["status"] == "active"


# ---------------------------------------------------------------------------
# Records tests
# ---------------------------------------------------------------------------


class TestRecordsExtended:
    def test_records_list_help(self) -> None:
        result = runner.invoke(app, ["records", "list", "--help"])
        assert result.exit_code == 0

    def test_records_create_help(self) -> None:
        result = runner.invoke(app, ["records", "create", "--help"])
        assert result.exit_code == 0

    def test_records_delete_help(self) -> None:
        result = runner.invoke(app, ["records", "delete", "--help"])
        assert result.exit_code == 0

    def test_records_list_json_with_type_filter(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = [r for r in MOCK_DNS_RECORDS if r["type"] == "A"]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.records import list_

        list_(ctx, zone="kodeme.io", record_type="A")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert all(r["type"] == "A" for r in data)

    def test_records_list_json_all(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = MOCK_DNS_RECORDS
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.records import list_

        list_(ctx, zone="kodeme.io", record_type=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_records_create_posts_payload(self, mock_client: MagicMock) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.post.return_value = {"id": "rec_new", "type": "A", "name": "api.kodeme.io"}
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.records import create

        create(ctx, record_type="A", name="api.kodeme.io", content="1.2.3.5", ttl=1, proxied=True, zone="kodeme.io")
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["type"] == "A"
        assert payload["name"] == "api.kodeme.io"
        assert payload["proxied"] is True

    def test_records_delete_calls_api(self, mock_client: MagicMock) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.delete.return_value = {}
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.records import delete_

        delete_(ctx, record_id="rec_1", force=True, zone="kodeme.io")
        mock_client.delete.assert_called_once_with("/zones/zone_abc/dns_records/rec_1")


# ---------------------------------------------------------------------------
# WAF tests
# ---------------------------------------------------------------------------


class TestWAFExtended:
    def test_waf_list_help(self) -> None:
        result = runner.invoke(app, ["waf", "list", "--help"])
        assert result.exit_code == 0

    def test_waf_create_help(self) -> None:
        result = runner.invoke(app, ["waf", "create", "--help"])
        assert result.exit_code == 0

    def test_waf_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = MOCK_WAF_RULES
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.waf import list_

        list_(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["action"] == "block"

    def test_waf_list_empty(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = []
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.waf import list_

        list_(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_waf_create_calls_filters_then_rules(self, mock_client: MagicMock) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.post.side_effect = [
            [{"id": "filter_1"}],  # First call: filters
            [{"id": "rule_1"}],  # Second call: firewall/rules
        ]
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.waf import create

        create(ctx, expression='(ip.geoip.country eq "XX")', action="block", description=None, zone="kodeme.io")
        assert mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


class TestCacheExtended:
    def test_cache_status_help(self) -> None:
        result = runner.invoke(app, ["cache", "status", "--help"])
        assert result.exit_code == 0

    def test_cache_purge_all_help(self) -> None:
        result = runner.invoke(app, ["cache", "purge-all", "--help"])
        assert result.exit_code == 0

    def test_cache_purge_help(self) -> None:
        result = runner.invoke(app, ["cache", "purge", "--help"])
        assert result.exit_code == 0

    def test_cache_status_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.side_effect = [
            {"value": "aggressive"},  # cache_level
            {"value": 14400},  # browser_cache_ttl
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.cache import status

        status(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data["zone"] == "kodeme.io"
        assert data["cache_level"] == "aggressive"
        assert data["browser_cache_ttl"] == 14400

    def test_cache_purge_all_calls_api(self, mock_client: MagicMock) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.post.return_value = {"id": "purge_1"}
        actx = _make_actx(json_mode=False, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.cache import purge_all

        purge_all(ctx, zone="kodeme.io", confirm=True)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/purge_cache" in call_args[0][0]
        assert call_args[1]["json"]["purge_everything"] is True

    def test_cache_purge_specific_urls(self, mock_client: MagicMock) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.post.return_value = {}
        actx = _make_actx(json_mode=False, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.cache import purge

        urls = ["https://kodeme.io/page1", "https://kodeme.io/page2"]
        purge(ctx, urls=urls, zone="kodeme.io")
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["files"] == urls


# ---------------------------------------------------------------------------
# Tunnels tests
# ---------------------------------------------------------------------------


class TestTunnels:
    def test_tunnels_help(self) -> None:
        result = runner.invoke(app, ["tunnels", "--help"])
        assert result.exit_code == 0

    def test_tunnels_list_help(self) -> None:
        result = runner.invoke(app, ["tunnels", "list", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# SSL tests
# ---------------------------------------------------------------------------


class TestSSLExtended:
    def test_ssl_status_help(self) -> None:
        result = runner.invoke(app, ["ssl", "status", "--help"])
        assert result.exit_code == 0

    def test_ssl_status_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_abc"
        mock_client.get.return_value = {"value": "strict"}
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cf.commands.ssl import status

        status(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data["zone"] == "kodeme.io"
        assert data["ssl_mode"] == "strict"
