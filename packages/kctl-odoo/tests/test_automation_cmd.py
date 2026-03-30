"""Tests for automation command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError


def _make_actx(client=None):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_common import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestAutomationImport:
    def test_import(self):
        from kctl_odoo.commands.automation_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.automation_cmd import (
            actions,
            disable,
            enable,
            history,
            rules,
            run,
        )

        assert callable(actions)
        assert callable(rules)
        assert callable(enable)
        assert callable(disable)
        assert callable(run)
        assert callable(history)


class TestAutomationActions:
    def test_actions_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import actions

        ctx = _make_ctx(actx)
        actions(ctx, model=None, limit=50)

    def test_actions_with_data(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Send Email on Confirmation",
                "model_id": [42, "sale.order"],
                "state": "email",
                "binding_type": "action",
                "usage": "ir_actions_server",
                "type": "ir.actions.server",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import actions

        ctx = _make_ctx(actx)
        actions(ctx, model=None, limit=50)

    def test_actions_with_model_filter(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import actions

        ctx = _make_ctx(actx)
        actions(ctx, model="sale.order", limit=50)
        call_args = c.search_read.call_args
        kwargs = call_args.kwargs if call_args.kwargs else {}
        domain = kwargs.get("domain", [])
        assert any("sale.order" in str(d) for d in domain)

    def test_actions_rpc_error(self):
        c = MagicMock()
        c.search_read.side_effect = RPCError({"message": "access denied"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import actions

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            actions(ctx, model=None, limit=50)


class TestAutomationRules:
    def test_rules_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import rules

        ctx = _make_ctx(actx)
        rules(ctx, model=None, limit=50)

    def test_rules_with_data(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 10,
                "name": "Auto-confirm sale orders",
                "model_id": [5, "sale.order"],
                "trigger": "on_write",
                "active": True,
                "last_run": "2026-03-28 08:00:00",
            },
            {
                "id": 11,
                "name": "Disabled rule",
                "model_id": [5, "sale.order"],
                "trigger": "on_create",
                "active": False,
                "last_run": False,
            },
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import rules

        ctx = _make_ctx(actx)
        rules(ctx, model=None, limit=50)

    def test_rules_with_model_filter(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import rules

        ctx = _make_ctx(actx)
        rules(ctx, model="purchase.order", limit=10)
        call_args = c.search_read.call_args
        kwargs = call_args.kwargs if call_args.kwargs else {}
        domain = kwargs.get("domain", [])
        assert any("purchase.order" in str(d) for d in domain)


class TestAutomationEnable:
    def test_enable_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import enable

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            enable(ctx, rule_id=999)

    def test_enable_already_active(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 10, "name": "My Rule", "active": True}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import enable

        ctx = _make_ctx(actx)
        enable(ctx, rule_id=10)
        # Should not call write
        c.execute_kw.assert_not_called()

    def test_enable_success(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 10, "name": "My Rule", "active": False}]
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import enable

        ctx = _make_ctx(actx)
        enable(ctx, rule_id=10)
        c.execute_kw.assert_called_once_with("base.automation", "write", [[10], {"active": True}])

    def test_enable_rpc_error(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 10, "name": "My Rule", "active": False}]
        c.execute_kw.side_effect = RPCError({"message": "access denied"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import enable

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            enable(ctx, rule_id=10)


class TestAutomationDisable:
    def test_disable_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import disable

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            disable(ctx, rule_id=999)

    def test_disable_already_inactive(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 10, "name": "My Rule", "active": False}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import disable

        ctx = _make_ctx(actx)
        disable(ctx, rule_id=10)
        c.execute_kw.assert_not_called()

    def test_disable_success(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 10, "name": "My Rule", "active": True}]
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import disable

        ctx = _make_ctx(actx)
        disable(ctx, rule_id=10)
        c.execute_kw.assert_called_once_with("base.automation", "write", [[10], {"active": False}])


class TestAutomationRun:
    def test_run_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import run

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            run(ctx, action_id=999, record_ids=None)

    def test_run_success(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 42, "name": "Send Email", "model_id": [5, "sale.order"], "state": "email"}]
        c.execute_kw.return_value = None
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import run

        ctx = _make_ctx(actx)
        run(ctx, action_id=42, record_ids=None)
        c.execute_kw.assert_called_once_with("ir.actions.server", "run", [[42]])

    def test_run_with_record_ids(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 42, "name": "Send Email", "model_id": [5, "sale.order"], "state": "email"}]
        c.execute_kw.return_value = None
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import run

        ctx = _make_ctx(actx)
        run(ctx, action_id=42, record_ids="1,2,3")
        c.execute_kw.assert_called_once_with("ir.actions.server", "run", [[42]], {"context": {"active_ids": [1, 2, 3]}})

    def test_run_invalid_record_ids(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 42, "name": "Send Email", "model_id": [5, "sale.order"], "state": "email"}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import run

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            run(ctx, action_id=42, record_ids="abc,def")


class TestAutomationHistory:
    def test_history_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import history

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            history(ctx, rule_id=999, limit=20)

    def test_history_with_logs(self):
        c = MagicMock()
        # First call: base.automation lookup
        # Second call: ir.logging lookup
        c.search_read.side_effect = [
            [{"id": 10, "name": "My Rule", "model_id": [5, "sale.order"], "last_run": "2026-03-28 08:00:00"}],
            [
                {
                    "create_date": "2026-03-28 08:00:01",
                    "level": "INFO",
                    "message": "Rule executed",
                    "func": "10",
                    "name": "odoo.addons.base_automation",
                }
            ],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, rule_id=10, limit=20)

    def test_history_fallback_to_messages(self):
        c = MagicMock()
        # First call: base.automation lookup
        # Second call: ir.logging returns empty
        # Third call: mail.message lookup
        c.search_read.side_effect = [
            [{"id": 10, "name": "My Rule", "model_id": [5, "sale.order"], "last_run": False}],
            [],
            [
                {
                    "date": "2026-03-28 09:00:00",
                    "message_type": "comment",
                    "subtype_id": [1, "Discussions"],
                    "body": "<p>Rule triggered</p>",
                    "author_id": [1, "Administrator"],
                }
            ],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, rule_id=10, limit=20)

    def test_history_no_logs_found(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 10, "name": "My Rule", "model_id": [5, "sale.order"], "last_run": False}],
            [],  # ir.logging empty
            [],  # mail.message empty
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.automation_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, rule_id=10, limit=20)
