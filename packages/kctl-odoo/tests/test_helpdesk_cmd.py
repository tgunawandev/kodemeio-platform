"""Tests for helpdesk command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestHelpdeskImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.helpdesk_cmd import app

        assert app is not None


class TestHelpdeskSummary:
    def test_summary_no_helpdesk(self) -> None:
        """summary should handle helpdesk not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)

    def test_summary_with_data(self) -> None:
        """summary should display ticket counts by stage."""
        c = MagicMock()
        c.search_count.return_value = 1  # model_available -> True; sla_breaches = 1
        c.read_group.return_value = [
            {"stage_id": [1, "New"], "__count": 5},
            {"stage_id": [2, "In Progress"], "__count": 3},
            {"stage_id": [3, "Solved"], "__count": 10},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestHelpdeskTickets:
    def test_tickets_empty(self) -> None:
        """tickets should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import tickets

        ctx = _make_ctx(actx)
        tickets(ctx, stage=None, team=None, assigned=None, limit=50)

    def test_tickets_no_helpdesk(self) -> None:
        """tickets should handle helpdesk not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import tickets

        ctx = _make_ctx(actx)
        tickets(ctx, stage=None, team=None, assigned=None, limit=50)

    def test_tickets_with_results(self) -> None:
        """tickets should display results table."""
        c = MagicMock()
        c.search_count.return_value = 5
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Cannot login to system",
                "partner_id": [10, "Acme Corp"],
                "team_id": [1, "Support"],
                "stage_id": [2, "In Progress"],
                "priority": "2",
                "create_date": "2026-03-29 08:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import tickets

        ctx = _make_ctx(actx)
        tickets(ctx, stage="In Progress", team=None, assigned=None, limit=10)


class TestHelpdeskSlaBreaches:
    def test_sla_breaches_empty(self) -> None:
        """sla-breaches should handle no breaches."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import sla_breaches

        ctx = _make_ctx(actx)
        sla_breaches(ctx, limit=50)

    def test_sla_breaches_with_results(self) -> None:
        """sla-breaches should display breached tickets."""
        c = MagicMock()
        c.search_count.return_value = 3
        c.search_read.return_value = [
            {
                "id": 5,
                "name": "Critical bug in production",
                "team_id": [1, "Tier 2 Support"],
                "stage_id": [2, "In Progress"],
                "priority": "3",
                "sla_deadline": "2026-03-28 12:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import sla_breaches

        ctx = _make_ctx(actx)
        sla_breaches(ctx, limit=20)


class TestHelpdeskTeamLoad:
    def test_team_load_empty(self) -> None:
        """team-load should handle no tickets."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.read_group.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import team_load

        ctx = _make_ctx(actx)
        team_load(ctx)

    def test_team_load_with_results(self) -> None:
        """team-load should display ticket count per team."""
        c = MagicMock()
        c.search_count.return_value = 10
        c.read_group.return_value = [
            {"team_id": [1, "Support"], "__count": 7},
            {"team_id": [2, "Tier 2"], "__count": 3},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.helpdesk_cmd import team_load

        ctx = _make_ctx(actx)
        team_load(ctx)
