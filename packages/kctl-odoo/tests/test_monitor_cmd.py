"""Tests for monitor command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import click
import pytest
import typer
from kctl_common import Output

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client=None, json_mode=False):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = json_mode
    actx.client = client or MagicMock()
    actx.output = Output(json_mode=json_mode)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestMonitorImport:
    def test_import_app(self):
        from kctl_odoo.commands.monitor_cmd import app

        assert app is not None

    def test_all_commands_registered(self):
        from kctl_odoo.commands.monitor_cmd import app

        command_names = {cmd.name for cmd in app.registered_commands}
        assert "run" in command_names
        assert "thresholds" in command_names
        assert "prometheus" in command_names
        assert "gatus-export" in command_names
        assert "glitchtip-export" in command_names
        assert "history" in command_names


class TestMonitorRun:
    def test_run_healthy(self):
        """All checks pass — no exception raised."""
        c = MagicMock()
        # search_read returns empty (no custom thresholds, connectivity check via search_read)
        # For connectivity we use search_read, then _get_threshold also uses search_read
        c.search_read.return_value = [{"id": 1}]
        # search_count calls: stuck modules, mail sent, mail failed, stale crons, pending queue jobs
        c.search_count.side_effect = [0, 5, 0, 0, 10]

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import run

        ctx = _make_ctx(actx)
        # Should not raise Exit
        run(ctx, strict=False)

    def test_run_fail_on_stuck_modules(self):
        """Stuck modules cause a fail exit."""
        c = MagicMock()
        c.search_read.return_value = []  # no custom thresholds
        # stuck_count = 3, then mail_sent=0, mail_failed=0, stale=0, queue=10
        c.search_count.side_effect = [3, 0, 0, 0, 10]

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import run

        ctx = _make_ctx(actx)
        with pytest.raises(click.exceptions.Exit) as exc_info:
            run(ctx, strict=False)
        assert exc_info.value.exit_code == 1

    def test_run_strict_exits_on_warn(self):
        """With --strict, warnings also cause exit 1."""
        c = MagicMock()
        c.search_read.return_value = []  # no custom thresholds
        # no stuck modules, no mail failure, stale_count=2 (triggers warn), queue=10
        c.search_count.side_effect = [0, 5, 0, 2, 10]

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import run

        ctx = _make_ctx(actx)
        with pytest.raises(click.exceptions.Exit) as exc_info:
            run(ctx, strict=True)
        assert exc_info.value.exit_code == 1


class TestMonitorThresholds:
    def test_show_thresholds(self, capsys):
        """Displays current thresholds when no --set given."""
        c = MagicMock()
        c.search_read.return_value = []  # no custom params stored

        actx = _make_actx(client=c, json_mode=True)
        from kctl_odoo.commands.monitor_cmd import thresholds

        ctx = _make_ctx(actx)
        thresholds(ctx, set_value=None)

        import json

        output = json.loads(capsys.readouterr().out)
        # Should be a list of threshold dicts
        assert isinstance(output, list)
        keys = {item["key"] for item in output}
        assert "mail_failure_rate" in keys
        assert "cron_stale_hours" in keys
        assert "pending_queue_jobs" in keys

    def test_set_threshold(self):
        """Setting a valid threshold calls write or create."""
        c = MagicMock()
        c.search.return_value = []  # no existing record

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import thresholds

        ctx = _make_ctx(actx)
        thresholds(ctx, set_value="mail_failure_rate=10")

        c.create.assert_called_once()

    def test_set_invalid_key(self):
        """Setting an unknown key exits 1."""
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import thresholds

        ctx = _make_ctx(actx)
        with pytest.raises(click.exceptions.Exit) as exc_info:
            thresholds(ctx, set_value="unknown_key=5")
        assert exc_info.value.exit_code == 1

    def test_set_non_integer_value(self):
        """Setting a non-integer value exits 1."""
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import thresholds

        ctx = _make_ctx(actx)
        with pytest.raises(click.exceptions.Exit) as exc_info:
            thresholds(ctx, set_value="mail_failure_rate=abc")
        assert exc_info.value.exit_code == 1


class TestMonitorPrometheus:
    def test_prometheus_output(self, capsys):
        """Output contains expected metric lines."""
        c = MagicMock()
        # search_count calls in order: modules_installed, mail_failed, cron_active, queue_pending, users_active
        c.search_count.side_effect = [491, 204, 107, 43, 5]

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import prometheus

        ctx = _make_ctx(actx)
        prometheus(ctx, prefix="kctl_odoo")

        captured = capsys.readouterr().out
        assert "kctl_odoo_modules_installed 491" in captured
        assert "kctl_odoo_mail_failed 204" in captured
        assert "kctl_odoo_cron_active 107" in captured
        assert "kctl_odoo_queue_pending 43" in captured
        assert "kctl_odoo_users_active 5" in captured

    def test_prometheus_custom_prefix(self, capsys):
        """Custom prefix is applied to all metric names."""
        c = MagicMock()
        c.search_count.side_effect = [100, 0, 50, 0, 3]

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import prometheus

        ctx = _make_ctx(actx)
        prometheus(ctx, prefix="myodoo")

        captured = capsys.readouterr().out
        assert "myodoo_modules_installed 100" in captured
        assert "myodoo_users_active 3" in captured

    def test_prometheus_json_output(self, capsys):
        """JSON mode returns list of metric dicts."""
        c = MagicMock()
        c.search_count.side_effect = [491, 204, 107, 43, 5]

        actx = _make_actx(client=c, json_mode=True)
        from kctl_odoo.commands.monitor_cmd import prometheus

        ctx = _make_ctx(actx)
        prometheus(ctx, prefix="kctl_odoo")

        import json

        output = json.loads(capsys.readouterr().out)
        assert isinstance(output, list)
        metrics = {item["metric"]: item["value"] for item in output}
        assert metrics["kctl_odoo_modules_installed"] == 491
        assert metrics["kctl_odoo_mail_failed"] == 204


class TestMonitorGatusExport:
    def test_gatus_export_contains_yaml(self, capsys):
        """Output contains valid YAML endpoint blocks."""
        c = MagicMock()
        c._url = "https://odoo.example.com"

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import gatus_export

        ctx = _make_ctx(actx)
        gatus_export(ctx)

        captured = capsys.readouterr().out
        assert "endpoints:" in captured
        assert "odoo-web" in captured
        assert "odoo-jsonrpc" in captured
        assert "https://odoo.example.com" in captured

    def test_gatus_export_json(self, capsys):
        """JSON mode returns yaml string and base_url."""
        c = MagicMock()
        c._url = "https://odoo.example.com"

        actx = _make_actx(client=c, json_mode=True)
        from kctl_odoo.commands.monitor_cmd import gatus_export

        ctx = _make_ctx(actx)
        gatus_export(ctx)

        import json

        output = json.loads(capsys.readouterr().out)
        assert "yaml" in output
        assert "base_url" in output
        assert output["base_url"] == "https://odoo.example.com"


class TestMonitorGlitchtipExport:
    def test_no_dsn_configured(self, capsys):
        """When no DSN in config_parameter, warns and shows instructions."""
        c = MagicMock()
        c.search_read.return_value = []

        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import glitchtip_export

        ctx = _make_ctx(actx)
        glitchtip_export(ctx)
        # Should not raise

    def test_dsn_configured_json(self, capsys):
        """When DSN is set, JSON output includes dsn value."""
        c = MagicMock()
        c.search_read.return_value = [{"value": "https://key@glitchtip.example.com/1"}]

        actx = _make_actx(client=c, json_mode=True)
        from kctl_odoo.commands.monitor_cmd import glitchtip_export

        ctx = _make_ctx(actx)
        glitchtip_export(ctx)

        import json

        output = json.loads(capsys.readouterr().out)
        assert output["dsn_configured"] is True
        assert "glitchtip.example.com" in output["dsn"]


class TestMonitorHistory:
    def test_history_shows_instructions(self, capsys):
        """History command outputs helpful instructions."""
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.monitor_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, days=7)
        # Should not raise

    def test_history_json(self, capsys):
        """JSON mode returns expected structure."""
        c = MagicMock()
        actx = _make_actx(client=c, json_mode=True)
        from kctl_odoo.commands.monitor_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, days=14)

        import json

        output = json.loads(capsys.readouterr().out)
        assert output["days"] == 14
        assert "message" in output
