"""Tests for command-level logic using mocked CloudflareClient."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import click
import pytest

from tests.conftest import _make_actx, _make_ctx

# ---------------------------------------------------------------------------
# zones
# ---------------------------------------------------------------------------


class TestZones:
    def test_zones_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {"name": "kodeme.io", "status": "active", "plan": {"name": "Free"}, "name_servers": ["ns1", "ns2"]},
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.zones import list_

        list_(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "kodeme.io"

    def test_zones_get_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get_zone_id.return_value = "zone_123"
        mock_client.get.return_value = {
            "id": "zone_123",
            "name": "kodeme.io",
            "status": "active",
            "plan": {"name": "Free"},
            "name_servers": ["ns1.cloudflare.com"],
        }
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.zones import get

        get(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "kodeme.io"
        assert data["id"] == "zone_123"


# ---------------------------------------------------------------------------
# records
# ---------------------------------------------------------------------------


class TestRecords:
    def test_records_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {"id": "rec_1", "type": "A", "name": "kodeme.io", "content": "1.2.3.4", "ttl": 1, "proxied": True}
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.records import list_

        list_(ctx, zone=None, record_type=None)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["type"] == "A"

    def test_records_create(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": "rec_new"}
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.records import create

        create(ctx, record_type="A", name="test", content="1.2.3.4", ttl=1, proxied=False, zone="kodeme.io")
        mock_client.post.assert_called_once()


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


class TestHealth:
    def _setup_healthy_client(self, mock_client: MagicMock) -> None:
        """Configure mock_client to pass all 6 health checks."""
        mock_client.check_health.return_value = {"status": "active"}
        mock_client.account_id = "test_account_id"

        def _get_side_effect(path: str, **kwargs: object) -> object:
            if path == "/zones":
                return [{"id": "z1", "name": "kodeme.io", "status": "active"}]
            if "/settings/ssl" in path:
                return {"value": "full"}
            if "/cfd_tunnel" in path:
                return [{"name": "main", "status": "healthy", "connections": []}]
            if "/accounts/" in path and "cfd_tunnel" not in path and "r2" not in path:
                return {"name": "Test Account"}
            return []

        mock_client.get.side_effect = _get_side_effect

    def test_health_check_ok(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        self._setup_healthy_client(mock_client)
        actx = _make_actx(json_mode=True, client=mock_client)
        actx.profile = None
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.health import check

        check(ctx, watch=False, interval=10, notify=False)

        data = json.loads(capsys.readouterr().out)
        assert data["healthy"] is True
        assert data["passed"] == data["total"]

    def test_health_check_fail(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_cloudflare.core.exceptions import ConnectionError as KctlConnectionError

        mock_client.check_health.side_effect = KctlConnectionError("https://api.cloudflare.com", None)
        mock_client.account_id = ""
        mock_client.get.return_value = []
        actx = _make_actx(json_mode=True, client=mock_client)
        actx.profile = None
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.health import check

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            check(ctx, watch=False, interval=10, notify=False)

        data = json.loads(capsys.readouterr().out)
        assert data["healthy"] is False


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_cache_status_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = {"value": "aggressive"}
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.cache import status

        status(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# ssl
# ---------------------------------------------------------------------------


class TestSsl:
    def test_ssl_status_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = {"value": "strict"}
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.ssl import status

        status(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# tunnels
# ---------------------------------------------------------------------------


class TestTunnels:
    def test_tunnels_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {"name": "kodeme-tunnel", "id": "tun_abc123", "status": "healthy", "connections": [{}]},
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.tunnels import list_

        list_(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "kodeme-tunnel"

    def test_tunnels_get_no_account(self, mock_client: MagicMock) -> None:
        """tunnels get should fail with helpful error if no account_id."""
        mock_client.account_id = ""
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.tunnels import get

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            get(ctx, name="test-tunnel")


# ---------------------------------------------------------------------------
# waf
# ---------------------------------------------------------------------------


class TestWaf:
    def test_waf_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "rule_1",
                "action": "block",
                "filter": {"expression": "ip.src eq 1.2.3.4"},
                "priority": 1,
                "paused": False,
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.waf import list_

        list_(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["action"] == "block"


# ---------------------------------------------------------------------------
# workers
# ---------------------------------------------------------------------------


class TestWorkers:
    def test_workers_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {"id": "my-worker", "etag": "abc123def456", "modified_on": "2025-01-01T00:00:00Z", "handlers": ["fetch"]},
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.workers import list_

        list_(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["id"] == "my-worker"


# ---------------------------------------------------------------------------
# email routing
# ---------------------------------------------------------------------------


class TestEmailRouting:
    def test_email_routing_status_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = {"enabled": True, "name": "kodeme.io"}
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.email_routing import status

        status(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert data["enabled"] is True


# ---------------------------------------------------------------------------
# page rules
# ---------------------------------------------------------------------------


class TestPageRules:
    def test_page_rules_list_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "pr_1",
                "targets": [{"constraint": {"value": "*.kodeme.io/*"}}],
                "actions": [{"id": "always_use_https"}],
                "priority": 1,
                "status": "active",
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.page_rules import list_

        list_(ctx, zone="kodeme.io")

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# access
# ---------------------------------------------------------------------------


class TestAccess:
    def test_access_apps_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {
                "id": "app_1",
                "name": "Admin",
                "domain": "admin.kodeme.io",
                "type": "self_hosted",
                "session_duration": "24h",
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_cloudflare.commands.access import apps

        apps(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Admin"


# ---------------------------------------------------------------------------
# shared utils: resolve_zone / require_account
# ---------------------------------------------------------------------------


class TestSharedHelpers:
    def test_resolve_zone_with_explicit(self, mock_client: MagicMock) -> None:
        from kctl_cloudflare.core.utils import resolve_zone

        actx = _make_actx(client=mock_client)
        assert resolve_zone(actx, "kodeme.io") == "kodeme.io"

    def test_resolve_zone_auto_default(self, mock_client: MagicMock) -> None:
        from kctl_cloudflare.core.utils import resolve_zone

        mock_client.get.return_value = [{"name": "kodeme.io"}]
        actx = _make_actx(client=mock_client)
        assert resolve_zone(actx, None) == "kodeme.io"

    def test_resolve_zone_no_zones(self, mock_client: MagicMock) -> None:
        from kctl_cloudflare.core.utils import resolve_zone

        mock_client.get.return_value = []
        actx = _make_actx(client=mock_client)
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            resolve_zone(actx, None)

    def test_require_account_present(self, mock_client: MagicMock) -> None:
        from kctl_cloudflare.core.utils import require_account

        mock_client.account_id = "acct_123"
        actx = _make_actx(client=mock_client)
        assert require_account(actx) == "acct_123"

    def test_require_account_missing(self, mock_client: MagicMock) -> None:
        from kctl_cloudflare.core.utils import require_account

        mock_client.account_id = ""
        actx = _make_actx(client=mock_client)
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            require_account(actx)


# ---------------------------------------------------------------------------
# delete protection — comprehensive
# ---------------------------------------------------------------------------


class TestDeleteProtection:
    """ALL delete commands require --force flag."""

    def _assert_blocked(self, func: object, *args: object, **kwargs: object) -> None:
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            func(*args, **kwargs)  # type: ignore[operator]

    def test_records_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.records import delete_

        self._assert_blocked(delete_, ctx, record_id="rec_123", force=False, zone="kodeme.io")

    def test_records_delete_with_force(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.records import delete_

        delete_(ctx, record_id="rec_123", force=True, zone="kodeme.io")
        mock_client.delete.assert_called_once()

    def test_zone_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.zones import delete_

        self._assert_blocked(delete_, ctx, zone="kodeme.io", force=False)

    def test_tunnel_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.tunnels import delete_

        self._assert_blocked(delete_, ctx, tunnel_id="tun_123", force=False)

    def test_r2_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.r2 import delete_

        self._assert_blocked(delete_, ctx, name="my-bucket", force=False)

    def test_page_rules_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.page_rules import delete_

        self._assert_blocked(delete_, ctx, rule_id="rule_123", force=False, zone="kodeme.io")

    def test_worker_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.workers import delete_

        self._assert_blocked(delete_, ctx, script_name="my-worker", force=False)

    def test_waf_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.waf import delete_

        self._assert_blocked(delete_, ctx, rule_id="rule_123", force=False, zone="kodeme.io")

    def test_email_routing_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.email_routing import delete_rule

        self._assert_blocked(delete_rule, ctx, rule_id="rule_123", force=False, zone="kodeme.io")

    def test_ssl_delete_origin_cert_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.ssl import delete_origin_cert

        self._assert_blocked(delete_origin_cert, ctx, cert_id="cert_123", force=False)

    def test_access_delete_group_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.access import delete_group

        self._assert_blocked(delete_group, ctx, group_id="grp_123", force=False)

    def test_workers_delete_kv_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.workers import delete_kv

        self._assert_blocked(delete_kv, ctx, namespace_id="ns_123", force=False)

    def test_workers_delete_route_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.workers import delete_route

        self._assert_blocked(delete_route, ctx, route_id="rt_123", force=False, zone="kodeme.io")

    def test_redirects_delete_list_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.redirects import delete_list

        self._assert_blocked(delete_list, ctx, list_id="lst_123", force=False)

    def test_redirects_delete_item_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.redirects import delete_item

        self._assert_blocked(delete_item, ctx, list_id="lst_123", item_id="itm_456", force=False)

    # --- New resource delete protection ---

    def test_ip_rule_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.waf import delete_ip_rule

        self._assert_blocked(delete_ip_rule, ctx, rule_id="ipr_1", force=False, zone="kodeme.io")

    def test_rate_limit_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.waf import delete_rate_limit

        self._assert_blocked(delete_rate_limit, ctx, rule_id="rl_1", force=False, zone="kodeme.io")

    def test_access_app_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.access import delete_app

        self._assert_blocked(delete_app, ctx, app_id="app_1", force=False)

    def test_access_policy_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.access import delete_policy

        self._assert_blocked(delete_policy, ctx, app_id="app_1", policy_id="pol_1", force=False)

    def test_service_token_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.access import delete_service_token

        self._assert_blocked(delete_service_token, ctx, token_id="tok_1", force=False)

    def test_workers_cron_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.workers import delete_cron_triggers

        self._assert_blocked(delete_cron_triggers, ctx, script_name="my-worker", force=False)

    def test_custom_hostname_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.custom_hostnames import delete_

        self._assert_blocked(delete_, ctx, hostname_id="ch_1", force=False, zone="kodeme.io")

    def test_load_balancer_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.load_balancers import delete_

        self._assert_blocked(delete_, ctx, lb_id="lb_1", force=False, zone="kodeme.io")

    def test_lb_pool_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.load_balancers import delete_pool

        self._assert_blocked(delete_pool, ctx, pool_id="pool_1", force=False)

    def test_lb_monitor_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.load_balancers import delete_monitor

        self._assert_blocked(delete_monitor, ctx, monitor_id="mon_1", force=False)

    def test_waiting_room_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.waiting_rooms import delete_

        self._assert_blocked(delete_, ctx, room_id="wr_1", force=False, zone="kodeme.io")

    def test_spectrum_delete_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.spectrum import delete_

        self._assert_blocked(delete_, ctx, app_id="spec_1", force=False, zone="kodeme.io")


# ---------------------------------------------------------------------------
# new resource commands (read paths)
# ---------------------------------------------------------------------------


class TestNewResources:
    def test_custom_hostnames_list(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "ch_1",
                "hostname": "app.example.com",
                "status": "active",
                "ssl": {"status": "active"},
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.custom_hostnames import list_

        list_(ctx, zone="kodeme.io", hostname=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_load_balancers_list(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "lb_1",
                "name": "my-lb",
                "default_pools": ["p1"],
                "fallback_pool": "p1",
                "proxied": True,
                "enabled": True,
            }
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.load_balancers import list_

        list_(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_waiting_rooms_list(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "wr_1",
                "name": "lobby",
                "host": "app.kodeme.io",
                "path": "/",
                "total_active_users": 100,
                "new_users_per_minute": 50,
                "status": "active",
            }
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.waiting_rooms import list_

        list_(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_spectrum_list(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {
                "id": "sp_1",
                "protocol": "tcp/22",
                "dns": {"name": "ssh.kodeme.io"},
                "origin_direct": ["tcp://1.2.3.4:22"],
                "ip_firewall": True,
                "proxy_protocol": "off",
                "created_on": "2025-01-01T00:00:00Z",
            }
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.spectrum import list_

        list_(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_argo_status(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = {"value": "on"}
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.argo import status

        status(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# completed resource operations (DNS, tunnels, pages, R2)
# ---------------------------------------------------------------------------


class TestCompletedResources:
    """Tests for the newly completed CRUD operations."""

    def test_records_get_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = {
            "type": "A",
            "name": "app.kodeme.io",
            "content": "1.2.3.4",
            "ttl": 1,
            "proxied": True,
            "zone_name": "kodeme.io",
            "created_on": "2025-01-01T00:00:00Z",
            "modified_on": "2025-01-01T00:00:00Z",
        }
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.records import get

        get(ctx, record_id="rec_1", zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data["type"] == "A"

    def test_records_scan(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.post.return_value = {"recs_added": 5, "total_records_parsed": 10}
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.records import scan

        scan(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert data["recs_added"] == 5

    def test_zones_settings(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.get.return_value = [
            {"id": "ssl", "value": "strict", "editable": True, "modified_on": "2025-01-01T00:00:00Z"},
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.zones import settings

        settings(ctx, zone="kodeme.io")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["id"] == "ssl"

    def test_tunnels_connections(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {
                "id": "conn_1",
                "client_id": "client_abc",
                "opened_at": "2025-01-01T00:00:00Z",
                "origin_ip": "10.0.0.1",
                "is_pending_reconnect": False,
            },
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.tunnels import connections

        connections(ctx, tunnel_id="tun_123")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_tunnels_clean_blocked(self, mock_client: MagicMock) -> None:
        mock_client.account_id = "acct_123"
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.tunnels import clean_connections

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            clean_connections(ctx, tunnel_id="tun_123", force=False)

    def test_pages_projects(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {
                "name": "my-site",
                "subdomain": "my-site.pages.dev",
                "production_branch": "main",
                "created_on": "2025-01-01T00:00:00Z",
            },
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.pages import projects

        projects(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "my-site"

    def test_pages_delete_project_blocked(self, mock_client: MagicMock) -> None:
        mock_client.account_id = "acct_123"
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.pages import delete_project

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            delete_project(ctx, name="my-site", force=False)

    def test_pages_delete_deployment_blocked(self, mock_client: MagicMock) -> None:
        mock_client.account_id = "acct_123"
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.pages import delete_deployment

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            delete_deployment(ctx, project_name="my-site", deployment_id="dep_1", force=False)

    def test_pages_remove_domain_blocked(self, mock_client: MagicMock) -> None:
        mock_client.account_id = "acct_123"
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.pages import remove_domain

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            remove_domain(ctx, project_name="my-site", domain_name="app.kodeme.io", force=False)

    def test_r2_list_objects(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.account_id = "acct_123"
        mock_client.get.return_value = [
            {"key": "file.txt", "size": 1024, "last_modified": "2025-01-01T00:00:00Z", "etag": "abc123"},
        ]
        ctx = _make_ctx(_make_actx(json_mode=True, client=mock_client))
        from kctl_cloudflare.commands.r2 import list_objects

        list_objects(ctx, bucket_name="my-bucket", prefix=None, limit=100)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_r2_delete_object_blocked(self, mock_client: MagicMock) -> None:
        mock_client.account_id = "acct_123"
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.r2 import delete_object

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            delete_object(ctx, bucket_name="my-bucket", key="file.txt", force=False)

    def test_zones_hold_release_blocked(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx(_make_actx(client=mock_client))
        from kctl_cloudflare.commands.zones import release_hold

        # release_hold doesn't need --force (it's a release), just test it runs
        release_hold(ctx, zone="kodeme.io")
        mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------


class TestUtils:
    def test_human_size(self) -> None:
        from kctl_cloudflare.core.utils import human_size

        assert human_size(0) == "0.0 B"
        assert human_size(1024) == "1.0 KB"
        assert human_size(1024 * 1024) == "1.0 MB"
        assert human_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_mask_token(self) -> None:
        from kctl_cloudflare.core.utils import mask_token

        assert mask_token("") == "[dim]not set[/dim]"
        assert mask_token("short") == "****"
        result = mask_token("abcdefghijklmnop")
        assert result.startswith("abcd")
        assert result.endswith("mnop")
        assert "****" in result

    def test_status_color(self) -> None:
        from kctl_cloudflare.core.utils import status_color

        assert "[green]" in status_color("active")
        assert "[yellow]" in status_color("pending")
        assert status_color("unknown") == "unknown"


# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------


class TestPlugins:
    def test_discover_no_plugins(self) -> None:
        import typer

        from kctl_cloudflare.core.plugins import discover_and_load_plugins

        test_app = typer.Typer()
        loaded = discover_and_load_plugins(test_app)
        assert loaded == []


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_config_expand_token(self) -> None:
        import os

        from kctl_cloudflare.core.config import expand_env

        os.environ["TEST_CF_TOKEN"] = "my_secret_token"
        assert expand_env("${TEST_CF_TOKEN}") == "my_secret_token"
        assert expand_env("plain_token") == "plain_token"
        del os.environ["TEST_CF_TOKEN"]

    def test_config_resolve_active_profile(self) -> None:
        from kctl_cloudflare.core.config import resolve_active_profile_name

        assert resolve_active_profile_name("staging") == "staging"


# ---------------------------------------------------------------------------
# exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_not_found_error(self) -> None:
        from kctl_cloudflare.core.exceptions import NotFoundError

        err = NotFoundError("zone", "kodeme.io")
        assert "zone" in str(err)
        assert "kodeme.io" in str(err)
        assert err.resource_type == "zone"
        assert err.identifier == "kodeme.io"

    def test_connection_error(self) -> None:
        from kctl_cloudflare.core.exceptions import ConnectionError as KctlConnectionError

        err = KctlConnectionError("https://api.cloudflare.com", ValueError("timeout"))
        assert "api.cloudflare.com" in str(err)

    def test_kctl_error_hierarchy(self) -> None:
        from kctl_cloudflare.core.exceptions import (
            AuthenticationError,
            ConfigError,
            KctlError,
            NotFoundError,
        )

        assert issubclass(ConfigError, KctlError)
        assert issubclass(AuthenticationError, KctlError)
        assert issubclass(NotFoundError, KctlError)
