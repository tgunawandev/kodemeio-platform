"""Tests for approvals command group."""

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
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestApprovalsImport:
    def test_import(self):
        from kctl_odoo.commands.approvals_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.approvals_cmd import (
            approve,
            delegate,
            escalated,
            history,
            pending,
            reject,
            sla_status,
            summary,
        )

        assert callable(summary)
        assert callable(pending)
        assert callable(approve)
        assert callable(reject)
        assert callable(delegate)
        assert callable(history)
        assert callable(sla_status)
        assert callable(escalated)


class TestApprovalsSummary:
    def test_summary_no_tier_validation(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import summary

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            summary(ctx)

    def test_summary_with_data(self):
        c = MagicMock()
        # model_available checks: first call succeeds (tier.review available)
        # then pending/validated/rejected counts, then model_available for sla.violation
        c.search_count.side_effect = [0, 5, 3, 2, 0]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestApprovalsPending:
    def test_pending_no_module(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import pending

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            pending(ctx, review_type=None, user=None, limit=50)

    def test_pending_empty(self):
        c = MagicMock()
        c.search_count.return_value = 0  # model_available succeeds
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import pending

        ctx = _make_ctx(actx)
        pending(ctx, review_type=None, user=None, limit=50)

    def test_pending_with_data(self):
        c = MagicMock()
        c.search_count.return_value = 0  # model_available
        c.search_read.return_value = [
            {
                "id": 1,
                "model": "sale.order",
                "res_id": 42,
                "requested_by": [5, "John Doe"],
                "status": "pending",
                "review_date": "2026-03-28 10:00:00",
                "date": "2026-03-28 10:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import pending

        ctx = _make_ctx(actx)
        pending(ctx, review_type=None, user=None, limit=50)

    def test_pending_with_type_filter(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import pending

        ctx = _make_ctx(actx)
        pending(ctx, review_type="sale.order", user=None, limit=50)
        call_args = c.search_read.call_args
        kwargs = call_args.kwargs if call_args.kwargs else {}
        domain = kwargs.get("domain", [])
        assert any("sale.order" in str(d) for d in domain)


class TestApprovalsApprove:
    def test_approve_no_module(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import approve

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            approve(ctx, model="sale.order", res_id=42, comment=None, force=False)

    def test_approve_success(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import approve

        ctx = _make_ctx(actx)
        approve(ctx, model="sale.order", res_id=42, comment=None, force=False)
        c.execute_kw.assert_called_with("sale.order", "validate_tier", [[42]])

    def test_approve_rpc_error_without_force(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.execute_kw.side_effect = RPCError({"message": "not a reviewer"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import approve

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            approve(ctx, model="sale.order", res_id=42, comment=None, force=False)

    def test_approve_rpc_error_with_force(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.execute_kw.side_effect = RPCError({"message": "not a reviewer"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import approve

        ctx = _make_ctx(actx)
        # With force=True, should not raise
        approve(ctx, model="sale.order", res_id=42, comment=None, force=True)


class TestApprovalsReject:
    def test_reject_success(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import reject

        ctx = _make_ctx(actx)
        reject(ctx, model="sale.order", res_id=42, reason="Budget exceeded", force=False)
        # First call is reject_tier, second is message_post for reason
        assert c.execute_kw.call_count >= 1
        first_call = c.execute_kw.call_args_list[0]
        assert first_call[0][1] == "reject_tier"


class TestApprovalsDelegate:
    def test_delegate_no_module(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import delegate

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            delegate(ctx, model="sale.order", res_id=42, to_user="5")

    def test_delegate_with_numeric_user(self):
        c = MagicMock()
        c.search_count.return_value = 0  # approval.delegation available
        c.execute_kw.return_value = [10]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import delegate

        ctx = _make_ctx(actx)
        delegate(ctx, model="sale.order", res_id=42, to_user="5")
        # Should call create on approval.delegation
        create_call = c.execute_kw.call_args
        assert create_call[0][0] == "approval.delegation"
        assert create_call[0][1] == "create"

    def test_delegate_user_not_found(self):
        c = MagicMock()
        c.search_count.return_value = 0
        # First search_read for user lookup returns empty
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import delegate

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            delegate(ctx, model="sale.order", res_id=42, to_user="nonexistent.user")


class TestApprovalsHistory:
    def test_history_empty(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, user=None, limit=50)

    def test_history_with_data(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = [
            {
                "id": 10,
                "model": "purchase.order",
                "res_id": 7,
                "requested_by": [2, "Jane Smith"],
                "status": "approved",
                "review_date": "2026-03-27 14:00:00",
                "date": "2026-03-27 14:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import history

        ctx = _make_ctx(actx)
        history(ctx, user=None, limit=50)


class TestApprovalsSlaStatus:
    def test_sla_status_no_tier_validation(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import sla_status

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            sla_status(ctx)

    def test_sla_status_fallback_no_pending(self):
        c = MagicMock()
        # tier.review available, approval.sla.violation not available
        call_count = [0]

        def search_count_side_effect(model, domain):
            call_count[0] += 1
            if model == "tier.review" and call_count[0] == 1:
                return 0  # model_available check passes
            raise RPCError({"message": "model not found"})

        c.search_count.side_effect = search_count_side_effect
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import sla_status

        ctx = _make_ctx(actx)
        sla_status(ctx)


class TestApprovalsEscalated:
    def test_escalated_empty(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import escalated

        ctx = _make_ctx(actx)
        escalated(ctx, limit=50)

    def test_escalated_with_data(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = [
            {
                "id": 3,
                "model": "account.move",
                "res_id": 99,
                "requested_by": [1, "Admin"],
                "status": "pending",
                "review_date": "2026-03-01 09:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.approvals_cmd import escalated

        ctx = _make_ctx(actx)
        escalated(ctx, limit=50)
