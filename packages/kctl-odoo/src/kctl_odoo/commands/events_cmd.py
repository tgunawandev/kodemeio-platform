"""Events commands — event management and registrations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Events: event management and registrations.")

_EVENT_MODEL = "event.event"
_EVENT_HINT = "Events module is not installed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_events(
    ctx: typer.Context,
    upcoming: Annotated[bool, typer.Option("--upcoming", help="Only show upcoming events")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List events.

    Examples:
        kctl-odoo events list
        kctl-odoo events list --upcoming --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _EVENT_MODEL):
        out.warn(_EVENT_HINT)
        return

    domain: list = []
    if upcoming:
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        domain.append(("date_begin", ">=", now))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _EVENT_MODEL,
            domain=domain,
            fields=["name", "date_begin", "date_end", "seats_max", "seats_available", "state"],
            limit=limit,
            order="date_begin asc",
        )
    except RPCError as e:
        out.error(f"Failed to list events: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No events found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                str(r.get("date_begin", "")),
                str(r.get("date_end", "")),
                str(r.get("seats_max", 0)),
                str(r.get("seats_available", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "date_begin": r.get("date_begin"),
                "date_end": r.get("date_end"),
                "seats_max": r.get("seats_max"),
                "seats_available": r.get("seats_available"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Events ({len(records)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Start", ""),
            ("End", ""),
            ("Seats Max", ""),
            ("Available", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET
# ===================================================================


@app.command("get")
def get_event(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Event ID")],
) -> None:
    """Get event detail with registration count.

    Examples:
        kctl-odoo events get 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _EVENT_MODEL):
        out.warn(_EVENT_HINT)
        return

    try:
        records = c.read(  # type: ignore[attr-defined]
            _EVENT_MODEL,
            [event_id],
            [
                "name",
                "date_begin",
                "date_end",
                "seats_max",
                "seats_available",
                "state",
                "organizer_id",
                "tag_ids",
                "registration_ids",
            ],
        )
    except RPCError as e:
        out.error(f"Failed to fetch event {event_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Event not found: {event_id}")
        raise typer.Exit(1)

    rec = records[0]
    reg_count = len(rec.get("registration_ids", []))

    sections = [
        (
            "Event",
            [
                ("ID", str(rec["id"])),
                ("Name", rec.get("name", "")),
                ("Start", str(rec.get("date_begin", ""))),
                ("End", str(rec.get("date_end", ""))),
                ("State", str(rec.get("state", ""))),
                ("Organizer", _m2o_name(rec.get("organizer_id"))),
                ("Seats Max", str(rec.get("seats_max", 0))),
                ("Seats Available", str(rec.get("seats_available", 0))),
                ("Registrations", str(reg_count)),
            ],
        )
    ]

    json_result = {
        "id": rec["id"],
        "name": rec.get("name"),
        "date_begin": rec.get("date_begin"),
        "date_end": rec.get("date_end"),
        "state": rec.get("state"),
        "organizer": _m2o_name(rec.get("organizer_id")),
        "seats_max": rec.get("seats_max"),
        "seats_available": rec.get("seats_available"),
        "registration_count": reg_count,
    }

    out.detail("Event Detail", sections, data_for_json=json_result)


# ===================================================================
# REGISTRATIONS
# ===================================================================


@app.command("registrations")
def registrations(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Event ID")],
    state: Annotated[str | None, typer.Option("--state", help="Filter by state: draft, open, cancel, done")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List registrations for an event.

    Examples:
        kctl-odoo events registrations 5
        kctl-odoo events registrations 5 --state open
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "event.registration"):
        out.warn(_EVENT_HINT)
        return

    domain: list = [("event_id", "=", event_id)]
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "event.registration",
            domain=domain,
            fields=["name", "partner_id", "email", "phone", "state", "date_open"],
            limit=limit,
            order="date_open desc",
        )
    except RPCError as e:
        out.error(f"Failed to list registrations: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No registrations found for event {event_id}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                _m2o_name(r.get("partner_id")),
                str(r.get("email", "")),
                r.get("state", ""),
                str(r.get("date_open", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "partner": _m2o_name(r.get("partner_id")),
                "email": r.get("email"),
                "state": r.get("state"),
                "date_open": r.get("date_open"),
            }
        )

    out.table(
        f"Registrations for Event {event_id} ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Partner", ""), ("Email", ""), ("State", ""), ("Date", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CONFIRM REGISTRATION
# ===================================================================


@app.command("confirm-registration")
def confirm_registration(
    ctx: typer.Context,
    registration_id: Annotated[int, typer.Argument(help="Registration ID")],
) -> None:
    """Confirm an event registration.

    Examples:
        kctl-odoo events confirm-registration 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "event.registration"):
        out.warn(_EVENT_HINT)
        return

    try:
        c.execute_kw("event.registration", "action_confirm", [[registration_id]])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to confirm registration {registration_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Confirmed registration {registration_id}")

    if actx.json_mode:
        out.raw_json({"id": registration_id, "action": "confirmed"})


# ===================================================================
# CANCEL REGISTRATION
# ===================================================================


@app.command("cancel-registration")
def cancel_registration(
    ctx: typer.Context,
    registration_id: Annotated[int, typer.Argument(help="Registration ID")],
) -> None:
    """Cancel an event registration.

    Examples:
        kctl-odoo events cancel-registration 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "event.registration"):
        out.warn(_EVENT_HINT)
        return

    try:
        c.execute_kw("event.registration", "action_cancel", [[registration_id]])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to cancel registration {registration_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Cancelled registration {registration_id}")

    if actx.json_mode:
        out.raw_json({"id": registration_id, "action": "cancelled"})


# ===================================================================
# STATS
# ===================================================================


@app.command("stats")
def stats(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Event ID")],
) -> None:
    """Registration statistics for an event: total, confirmed, draft, cancelled, revenue.

    Examples:
        kctl-odoo events stats 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "event.registration"):
        out.warn(_EVENT_HINT)
        return

    try:
        groups = c.read_group(  # type: ignore[attr-defined]
            "event.registration",
            domain=[("event_id", "=", event_id)],
            fields=["state"],
            groupby=["state"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch stats for event {event_id}: {e}")
        raise typer.Exit(1) from e

    state_labels = {
        "draft": "Draft",
        "open": "Confirmed",
        "cancel": "Cancelled",
        "done": "Done",
    }

    buckets: dict[str, int] = {}
    for g in groups:
        st = g.get("state", "unknown")
        buckets[st] = g.get("__count", 0)

    total = sum(buckets.values())

    rows = []
    json_data: list[dict] = []
    for st, label in state_labels.items():
        count = buckets.get(st, 0)
        rows.append([label, str(count)])
        json_data.append({"state": st, "label": label, "count": count})

    rows.append(["[bold]Total[/bold]", f"[bold]{total}[/bold]"])
    json_data.append({"state": "total", "label": "Total", "count": total})

    out.table(
        f"Registration Stats for Event {event_id}",
        [("Status", ""), ("Count", "cyan")],
        rows,
        data_for_json={"event_id": event_id, "total": total, "by_state": json_data},
    )


# ===================================================================
# UPCOMING
# ===================================================================


@app.command("upcoming")
def upcoming(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Events starting within N days")] = 30,
) -> None:
    """List events starting within N days.

    Examples:
        kctl-odoo events upcoming
        kctl-odoo events upcoming --days 7
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _EVENT_MODEL):
        out.warn(_EVENT_HINT)
        return

    now = datetime.now(tz=UTC)
    cutoff = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [
        ("date_begin", ">=", now_str),
        ("date_begin", "<=", cutoff),
    ]

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _EVENT_MODEL,
            domain=domain,
            fields=["name", "date_begin", "date_end", "seats_max", "seats_available", "state"],
            limit=100,
            order="date_begin asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch upcoming events: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No events starting in the next {days} days.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                str(r.get("date_begin", "")),
                str(r.get("seats_available", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "date_begin": r.get("date_begin"),
                "seats_available": r.get("seats_available"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Upcoming Events (next {days} days, {len(records)} found)",
        [("ID", "dim"), ("Name", "cyan"), ("Start", ""), ("Available", ""), ("State", "")],
        rows,
        data_for_json=json_data,
    )
