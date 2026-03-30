"""Helpdesk commands — tickets, teams, SLA tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Helpdesk: tickets, teams, SLA tracking.")

_HELPDESK_MODEL = "helpdesk.ticket"
_HELPDESK_HINT = "Helpdesk module is not installed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _resolve_user(c: object, login_or_name: str) -> int:
    """Resolve user by login or name. Returns user ID."""
    recs = c.search_read(  # type: ignore[attr-defined]
        "res.users",
        ["|", ("login", "=", login_or_name), ("name", "ilike", login_or_name)],
        ["id", "name"],
        limit=1,
    )
    if not recs:
        raise typer.BadParameter(f"User not found: {login_or_name}")
    return recs[0]["id"]


def _get_last_stage(c: object) -> int:
    """Get the last helpdesk stage (highest sequence)."""
    stages = c.search_read(  # type: ignore[attr-defined]
        "helpdesk.stage",
        domain=[],
        fields=["id", "sequence", "name"],
        order="sequence desc",
        limit=1,
    )
    if not stages:
        raise typer.BadParameter("No helpdesk stages found.")
    return stages[0]["id"]


# ===================================================================
# SUMMARY
# ===================================================================


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """Helpdesk dashboard: ticket counts by stage and SLA breaches.

    Examples:
        kctl-odoo helpdesk summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    try:
        groups = c.read_group(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            domain=[],
            fields=["stage_id"],
            groupby=["stage_id"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch ticket summary: {e}")
        raise typer.Exit(1) from e

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
    sla_breaches = 0
    try:
        sla_breaches = c.search_count(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            [("sla_deadline", "<", now), ("sla_deadline", "!=", False)],
        )
    except RPCError:
        sla_breaches = 0

    total = sum(g.get("__count", 0) for g in groups)

    rows = []
    json_data: list[dict] = []
    for g in groups:
        stage = _m2o_name(g.get("stage_id"))
        count = g.get("__count", 0)
        rows.append([stage, str(count)])
        json_data.append({"stage": stage, "count": count})

    rows.append(["[bold]Total[/bold]", f"[bold]{total}[/bold]"])
    rows.append(["[red]SLA Breaches[/red]", f"[red]{sla_breaches}[/red]"])
    json_data.append({"stage": "total", "count": total})
    json_data.append({"stage": "sla_breaches", "count": sla_breaches})

    out.table(
        "Helpdesk Summary",
        [("Stage", ""), ("Count", "cyan")],
        rows,
        data_for_json={"stages": json_data, "sla_breaches": sla_breaches, "total": total},
    )


# ===================================================================
# TICKETS
# ===================================================================


@app.command("tickets")
def tickets(
    ctx: typer.Context,
    stage: Annotated[str | None, typer.Option("--stage", help="Filter by stage name")] = None,
    team: Annotated[str | None, typer.Option("--team", help="Filter by team name")] = None,
    assigned: Annotated[str | None, typer.Option("--assigned", help="Filter by assigned user login/name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List helpdesk tickets.

    Examples:
        kctl-odoo helpdesk tickets
        kctl-odoo helpdesk tickets --stage "In Progress" --limit 20
        kctl-odoo helpdesk tickets --team "Support"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    domain: list = []
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    if team:
        domain.append(("team_id.name", "ilike", team))
    if assigned:
        domain.append(("user_id.login", "=", assigned))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            domain=domain,
            fields=["name", "partner_id", "team_id", "stage_id", "priority", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list tickets: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No tickets found.")
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
                _m2o_name(r.get("team_id")),
                _m2o_name(r.get("stage_id")),
                str(r.get("priority", "0")),
                str(r.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "partner": _m2o_name(r.get("partner_id")),
                "team": _m2o_name(r.get("team_id")),
                "stage": _m2o_name(r.get("stage_id")),
                "priority": r.get("priority"),
                "create_date": r.get("create_date"),
            }
        )

    out.table(
        f"Helpdesk Tickets ({len(records)})",
        [
            ("ID", "dim"),
            ("Subject", "cyan"),
            ("Partner", ""),
            ("Team", ""),
            ("Stage", ""),
            ("Priority", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET TICKET
# ===================================================================


@app.command("get-ticket")
def get_ticket(
    ctx: typer.Context,
    ticket_id: Annotated[int, typer.Argument(help="Ticket ID")],
) -> None:
    """Get helpdesk ticket detail with messages.

    Examples:
        kctl-odoo helpdesk get-ticket 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    try:
        records = c.read(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            [ticket_id],
            [
                "name",
                "partner_id",
                "team_id",
                "stage_id",
                "priority",
                "create_date",
                "user_id",
                "description",
                "sla_deadline",
                "message_ids",
            ],
        )
    except RPCError as e:
        out.error(f"Failed to fetch ticket {ticket_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Ticket not found: {ticket_id}")
        raise typer.Exit(1)

    rec = records[0]
    sections = [
        (
            "Ticket",
            [
                ("ID", str(rec["id"])),
                ("Subject", rec.get("name", "")),
                ("Partner", _m2o_name(rec.get("partner_id"))),
                ("Team", _m2o_name(rec.get("team_id"))),
                ("Stage", _m2o_name(rec.get("stage_id"))),
                ("Assigned To", _m2o_name(rec.get("user_id"))),
                ("Priority", str(rec.get("priority", "0"))),
                ("SLA Deadline", str(rec.get("sla_deadline", ""))),
                ("Created", str(rec.get("create_date", ""))),
            ],
        )
    ]

    json_result = {
        "id": rec["id"],
        "name": rec.get("name"),
        "partner": _m2o_name(rec.get("partner_id")),
        "team": _m2o_name(rec.get("team_id")),
        "stage": _m2o_name(rec.get("stage_id")),
        "assigned_to": _m2o_name(rec.get("user_id")),
        "priority": rec.get("priority"),
        "sla_deadline": rec.get("sla_deadline"),
        "create_date": rec.get("create_date"),
        "messages": [],
    }

    out.detail("Ticket Detail", sections, data_for_json=json_result)

    # Messages
    msg_ids = rec.get("message_ids", [])
    if msg_ids:
        try:
            messages = c.read(  # type: ignore[attr-defined]
                "mail.message",
                msg_ids[:10],  # limit to last 10 messages
                ["author_id", "date", "body"],
            )
        except RPCError as e:
            out.warn(f"Failed to read messages: {e}")
            return

        rows = []
        msgs_json = []
        for m in messages:
            body_preview = (m.get("body", "") or "").replace("<p>", "").replace("</p>", "")[:80]
            rows.append([_m2o_name(m.get("author_id")), str(m.get("date", "")), body_preview])
            msgs_json.append({"author": _m2o_name(m.get("author_id")), "date": m.get("date"), "body": m.get("body")})

        json_result["messages"] = msgs_json

        out.table(
            f"Messages ({len(messages)})",
            [("Author", ""), ("Date", "dim"), ("Body", "")],
            rows,
            data_for_json=msgs_json,
        )


# ===================================================================
# CREATE TICKET
# ===================================================================


@app.command("create-ticket")
def create_ticket(
    ctx: typer.Context,
    subject: Annotated[str, typer.Argument(help="Ticket subject")],
    partner: Annotated[str | None, typer.Option("--partner", help="Partner name or ID")] = None,
    team: Annotated[str | None, typer.Option("--team", help="Team name or ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Priority: 0=Normal, 1=Low, 2=High, 3=Urgent")] = "1",
) -> None:
    """Create a new helpdesk ticket.

    Examples:
        kctl-odoo helpdesk create-ticket "Login issue"
        kctl-odoo helpdesk create-ticket "Bug report" --partner "Acme Corp" --priority 2
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    vals: dict = {"name": subject, "priority": priority}

    if partner:
        if partner.isdigit():
            vals["partner_id"] = int(partner)
        else:
            partners = c.search_read(  # type: ignore[attr-defined]
                "res.partner", [("name", "ilike", partner)], ["id", "name"], limit=1
            )
            if partners:
                vals["partner_id"] = partners[0]["id"]
            else:
                out.warn(f"Partner not found: {partner}, creating ticket without partner.")

    if team:
        if team.isdigit():
            vals["team_id"] = int(team)
        else:
            teams = c.search_read(  # type: ignore[attr-defined]
                "helpdesk.team", [("name", "ilike", team)], ["id", "name"], limit=1
            )
            if teams:
                vals["team_id"] = teams[0]["id"]
            else:
                out.warn(f"Team not found: {team}, creating ticket without team.")

    try:
        ticket_id = c.create(_HELPDESK_MODEL, vals)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to create ticket: {e}")
        raise typer.Exit(1) from e

    out.success(f"Created ticket ID {ticket_id}: {subject}")

    if actx.json_mode:
        out.raw_json({"id": ticket_id, "name": subject, "priority": priority})


# ===================================================================
# ASSIGN
# ===================================================================


@app.command("assign")
def assign(
    ctx: typer.Context,
    ticket_id: Annotated[int, typer.Argument(help="Ticket ID")],
    user: Annotated[str, typer.Argument(help="User login or name")],
) -> None:
    """Assign a helpdesk ticket to a user.

    Examples:
        kctl-odoo helpdesk assign 42 admin
        kctl-odoo helpdesk assign 42 "John Smith"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    try:
        user_id = _resolve_user(c, user)
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    try:
        c.write(_HELPDESK_MODEL, [ticket_id], {"user_id": user_id})  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to assign ticket {ticket_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Assigned ticket {ticket_id} to user ID {user_id} ({user})")

    if actx.json_mode:
        out.raw_json({"ticket_id": ticket_id, "user_id": user_id, "user": user})


# ===================================================================
# CLOSE
# ===================================================================


@app.command("close")
def close(
    ctx: typer.Context,
    ticket_id: Annotated[int, typer.Argument(help="Ticket ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Close a helpdesk ticket (move to last stage).

    Examples:
        kctl-odoo helpdesk close 42
        kctl-odoo helpdesk close 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    if not force and not typer.confirm(f"Close ticket {ticket_id}?"):
        raise typer.Exit(0)

    try:
        last_stage_id = _get_last_stage(c)
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    try:
        c.write(_HELPDESK_MODEL, [ticket_id], {"stage_id": last_stage_id})  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to close ticket {ticket_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Closed ticket {ticket_id} (stage ID: {last_stage_id})")

    if actx.json_mode:
        out.raw_json({"ticket_id": ticket_id, "stage_id": last_stage_id, "action": "closed"})


# ===================================================================
# SLA BREACHES
# ===================================================================


@app.command("sla-breaches")
def sla_breaches(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List tickets that have breached their SLA deadline.

    Examples:
        kctl-odoo helpdesk sla-breaches
        kctl-odoo helpdesk sla-breaches --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            domain=[("sla_deadline", "<", now), ("sla_deadline", "!=", False)],
            fields=["name", "partner_id", "team_id", "stage_id", "priority", "sla_deadline"],
            limit=limit,
            order="sla_deadline asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch SLA breaches: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No SLA breaches found.")
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
                _m2o_name(r.get("team_id")),
                _m2o_name(r.get("stage_id")),
                str(r.get("sla_deadline", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "team": _m2o_name(r.get("team_id")),
                "stage": _m2o_name(r.get("stage_id")),
                "sla_deadline": r.get("sla_deadline"),
            }
        )

    out.table(
        f"SLA Breaches ({len(records)})",
        [("ID", "dim"), ("Subject", "cyan"), ("Team", ""), ("Stage", ""), ("SLA Deadline", "red")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TEAM LOAD
# ===================================================================


@app.command("team-load")
def team_load(ctx: typer.Context) -> None:
    """Show ticket count per helpdesk team.

    Examples:
        kctl-odoo helpdesk team-load
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _HELPDESK_MODEL):
        out.warn(_HELPDESK_HINT)
        return

    try:
        groups = c.read_group(  # type: ignore[attr-defined]
            _HELPDESK_MODEL,
            domain=[],
            fields=["team_id"],
            groupby=["team_id"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch team load: {e}")
        raise typer.Exit(1) from e

    if not groups:
        out.info("No tickets found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for g in groups:
        team = _m2o_name(g.get("team_id"))
        count = g.get("__count", 0)
        rows.append([team, str(count)])
        json_data.append({"team": team, "ticket_count": count})

    out.table(
        "Ticket Load by Team",
        [("Team", "cyan"), ("Tickets", "")],
        rows,
        data_for_json=json_data,
    )
