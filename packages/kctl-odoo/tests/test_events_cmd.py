"""Tests for events command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_common import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestEventsImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.events_cmd import app

        assert app is not None


class TestEventsList:
    def test_list_empty(self) -> None:
        """list should handle no events."""
        c = MagicMock()
        c.search_count.return_value = 1  # model_available -> True
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import list_events

        ctx = _make_ctx(actx)
        list_events(ctx, upcoming=False, limit=50)

    def test_list_no_events_module(self) -> None:
        """list should handle events module not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import list_events

        ctx = _make_ctx(actx)
        list_events(ctx, upcoming=False, limit=50)

    def test_list_with_results(self) -> None:
        """list should display events table."""
        c = MagicMock()
        c.search_count.return_value = 3
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Annual Conference 2026",
                "date_begin": "2026-04-15 08:00:00",
                "date_end": "2026-04-15 17:00:00",
                "seats_max": 200,
                "seats_available": 150,
                "state": "confirm",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import list_events

        ctx = _make_ctx(actx)
        list_events(ctx, upcoming=True, limit=10)


class TestEventsRegistrations:
    def test_registrations_empty(self) -> None:
        """registrations should handle no registrations."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import registrations

        ctx = _make_ctx(actx)
        registrations(ctx, event_id=5, state=None, limit=50)

    def test_registrations_with_results(self) -> None:
        """registrations should display registration list."""
        c = MagicMock()
        c.search_count.return_value = 10
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "John Doe",
                "partner_id": [5, "Acme Corp"],
                "email": "john@acme.com",
                "state": "open",
                "date_open": "2026-03-20 10:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import registrations

        ctx = _make_ctx(actx)
        registrations(ctx, event_id=1, state="open", limit=20)


class TestEventsStats:
    def test_stats_empty(self) -> None:
        """stats should handle event with no registrations."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.read_group.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import stats

        ctx = _make_ctx(actx)
        stats(ctx, event_id=5)

    def test_stats_with_data(self) -> None:
        """stats should display registration breakdown."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.read_group.return_value = [
            {"state": "open", "__count": 50},
            {"state": "draft", "__count": 10},
            {"state": "cancel", "__count": 5},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import stats

        ctx = _make_ctx(actx)
        stats(ctx, event_id=1)


class TestEventsUpcoming:
    def test_upcoming_empty(self) -> None:
        """upcoming should handle no upcoming events."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import upcoming

        ctx = _make_ctx(actx)
        upcoming(ctx, days=30)

    def test_upcoming_with_results(self) -> None:
        """upcoming should display events starting soon."""
        c = MagicMock()
        c.search_count.return_value = 2
        c.search_read.return_value = [
            {
                "id": 3,
                "name": "Product Launch",
                "date_begin": "2026-04-05 09:00:00",
                "seats_available": 80,
                "state": "confirm",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.events_cmd import upcoming

        ctx = _make_ctx(actx)
        upcoming(ctx, days=7)
