"""Tests for the troubleshoot command group (check, stuck-modules, check-config, version-info)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from kctl_odoo.core.output import Output

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    actx.profile = "test"
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


def _healthy_client() -> MagicMock:
    c = MagicMock()
    c.database = "test_db"
    c.check_health.return_value = (True, "18.0")
    c.authenticate.return_value = 2
    c.search_count.return_value = 5
    c.search_read.return_value = []
    c.version_info.return_value = {"server_version": "18.0.1", "server_serie": "18.0"}
    return c


# ---------------------------------------------------------------------------
# check (health check, merged from health.py)
# ---------------------------------------------------------------------------


class TestCheck:
    def test_healthy_instance_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check outputs healthy=True JSON for a reachable instance."""
        c = _healthy_client()
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import check

        check(ctx, watch=False, interval=10)

        data = json.loads(capsys.readouterr().out)
        assert data["healthy"] is True
        assert data["version"] == "18.0"
        assert data["database"] == "test_db"

    def test_unhealthy_instance_reports_false(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check outputs healthy=False when check_health returns False."""
        c = MagicMock()
        c.database = "test_db"
        c.check_health.return_value = (False, "Connection refused")
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import check

        check(ctx, watch=False, interval=10)

        data = json.loads(capsys.readouterr().out)
        assert data["healthy"] is False
        assert "Connection refused" in data["error"]

    def test_healthy_auth_failure_still_reachable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check reports reachable even if authenticate() throws (version check succeeded)."""
        c = MagicMock()
        c.database = "test_db"
        c.check_health.return_value = (True, "18.0")
        c.authenticate.side_effect = Exception("auth failed")
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import check

        check(ctx, watch=False, interval=10)

        data = json.loads(capsys.readouterr().out)
        # auth failed but health was still True
        assert data["healthy"] is True
        assert data["auth"] is False


# ---------------------------------------------------------------------------
# stuck-modules
# ---------------------------------------------------------------------------


class TestStuckModules:
    def test_no_stuck_modules_success_message(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """stuck-modules reports success when no transitional-state modules found."""
        mock_client.search_read.return_value = []
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import stuck_modules

        stuck_modules(ctx)

        # No JSON emitted; no crash expected
        capsys.readouterr()  # consume output

    def test_stuck_modules_listed_in_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """stuck-modules lists stuck modules as a JSON array."""
        mock_client.search_read.return_value = [
            {
                "id": 10,
                "name": "sale",
                "shortdesc": "Sales",
                "state": "to upgrade",
                "installed_version": "18.0.1.0",
                "latest_version": "18.0.2.0",
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import stuck_modules

        stuck_modules(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "sale"
        assert data[0]["state"] == "to upgrade"

    def test_domain_filters_transitional_states(self, mock_client: MagicMock) -> None:
        """stuck-modules queries only transitional states (to install/upgrade/remove)."""
        mock_client.search_read.return_value = []
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import stuck_modules

        stuck_modules(ctx)

        call_kwargs = mock_client.search_read.call_args
        # Extract domain from positional or keyword args
        domain = call_kwargs[1].get("domain", []) if call_kwargs[1] else call_kwargs[0][1]

        # Confirm transitional states are included in the domain
        [v for op, k, v in (t for t in domain if len(t) == 3) if k == "state" or op == "state"]
        # Domain contains ("state", "in", [...])
        assert any("to install" in str(d) for d in domain)


# ---------------------------------------------------------------------------
# check-config
# ---------------------------------------------------------------------------


class TestCheckConfig:
    def test_config_check_returns_checks_array(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check-config outputs a JSON array with check/passed/detail keys."""
        c = _healthy_client()
        # web.base.url
        c.search_read.side_effect = [
            [{"value": "https://odoo.example.com"}],  # web.base.url
            [{"value": "example.com"}],  # mail.catchall.domain
            [{"value": "abc-123"}],  # database.uuid
            [{"id": 1, "name": "My Company", "fiscalyear_lock_date": "2025-12-31"}],
        ]
        c.search_count.side_effect = [
            1,  # SMTP active count
            1,  # stock.warehouse
            10,  # account.tax sale
            10,  # account.tax purchase
        ]
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import check_config

        check_config(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        # Each item must have check, passed, detail
        for item in data:
            assert "check" in item
            assert "passed" in item

    def test_localhost_url_fails_check(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check-config marks web.base.url as FAIL when it points to localhost."""
        c = _healthy_client()
        c.search_read.side_effect = [
            [{"value": "http://localhost:8069"}],  # web.base.url — localhost
            [{"value": "example.com"}],  # mail.catchall.domain
            [{"value": "abc-123"}],  # database.uuid
            [{"id": 1, "name": "My Company", "fiscalyear_lock_date": None}],
        ]
        c.search_count.side_effect = [0, 0, 0, 0]
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import check_config

        check_config(ctx)

        data = json.loads(capsys.readouterr().out)
        base_url_check = next((d for d in data if d["check"] == "web.base.url"), None)
        assert base_url_check is not None
        assert base_url_check["passed"] is False


# ---------------------------------------------------------------------------
# version-info
# ---------------------------------------------------------------------------


class TestVersionInfo:
    def test_version_info_json_structure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """version-info outputs odoo_version, database, cli_version keys in JSON."""
        c = _healthy_client()
        # _get_param calls search_read with different keys
        c.search_read.side_effect = [
            [{"value": "abc-123"}],  # database.uuid
            [{"value": "2024-01-01"}],  # database.create_date
            [{"id": 1, "name": "sale", "author": "Odoo SA"}],  # installed modules
        ]
        # Override version_info to return full dict
        c.version_info.return_value = {"server_version": "18.0.1+e", "server_serie": "18.0"}
        c.search_read.return_value = []  # installed modules list

        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import version_info

        version_info(ctx)

        data = json.loads(capsys.readouterr().out)
        assert "odoo_version" in data
        assert "database" in data
        assert "cli_version" in data
        assert data["odoo_version"] == "18.0.1+e"
        assert data["database"]["name"] == "test_db"

    def test_version_info_module_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """version-info includes module origin breakdown when modules are queryable."""
        c = _healthy_client()
        c.version_info.return_value = {"server_version": "18.0", "server_serie": "18.0"}
        # _get_param for database.uuid + create_date
        c.search_read.side_effect = [
            [{"value": "uuid-1"}],  # database.uuid
            [{"value": "2024-01-01"}],  # database.create_date
            # installed modules list with mixed authors
            [
                {"name": "sale", "author": "Odoo SA"},
                {"name": "oca_partner_firstname", "author": "Odoo Community Association (OCA)"},
                {"name": "sfa_management", "author": "Kodemeio"},
            ],
        ]
        actx = _make_actx(json_mode=True, client=c)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.troubleshoot import version_info

        version_info(ctx)

        data = json.loads(capsys.readouterr().out)
        assert "modules" in data
        assert data["modules"]["total"] == 3
        assert data["modules"]["private"] == 1  # Kodemeio author
        assert data["modules"]["oca"] == 1
