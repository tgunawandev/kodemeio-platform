"""Support ticket management commands — internal support, SLA, knowledge base."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Internal support: tickets, SLA, knowledge base.")

_SUPPORT_MODEL = "support.ticket"
_SUPPORT_HINT = "Support management module (support_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# TICKETS
# ===================================================================


@app.command("tickets")
def tickets(
    ctx: typer.Context,
    status: Annotated[str | None, typer.Option("--status", help="Filter by status (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List support tickets.

    Examples:
        kctl-odoo support tickets
        kctl-odoo support tickets --status open --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _SUPPORT_MODEL):
        out.warn(_SUPPORT_HINT)
        return

    domain: list = []
    if status:
        domain.append(("state", "ilike", status))

    preferred_fields = ["display_name", "category_id", "state", "priority", "user_id", "create_date"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _SUPPORT_MODEL,
            domain=domain,
            fields=preferred_fields,
            limit=limit,
            order="create_date desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _SUPPORT_MODEL,
                domain=domain,
                fields=["display_name", "state", "create_date"],
                limit=limit,
                order="create_date desc",
            )
        except RPCError as e:
            out.error(f"Failed to list support tickets: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No support tickets found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("category_id")),
                str(r.get("state", "")),
                str(r.get("priority", "")),
                _m2o_name(r.get("user_id")),
                str(r.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "category": _m2o_name(r.get("category_id")),
                "state": r.get("state"),
                "priority": r.get("priority"),
                "user": _m2o_name(r.get("user_id")),
                "create_date": r.get("create_date"),
            }
        )

    out.table(
        f"Support Tickets ({len(records)})",
        [
            ("ID", "dim"),
            ("Subject", "cyan"),
            ("Category", ""),
            ("Status", ""),
            ("Priority", ""),
            ("Assigned", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CREATE
# ===================================================================


@app.command("create")
def create(
    ctx: typer.Context,
    subject: Annotated[str, typer.Argument(help="Ticket subject")],
    category: Annotated[str | None, typer.Option("--category", help="Category name or ID")] = None,
    priority: Annotated[int, typer.Option("--priority", help="Priority: 0=Normal, 1=Low, 2=High, 3=Urgent")] = 1,
) -> None:
    """Create a new support ticket.

    Examples:
        kctl-odoo support create "Login issue"
        kctl-odoo support create "Database error" --category "Technical" --priority 2
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _SUPPORT_MODEL):
        out.warn(_SUPPORT_HINT)
        return

    vals: dict = {"name": subject, "priority": str(priority)}

    if category:
        if category.isdigit():
            vals["category_id"] = int(category)
        else:
            cats = c.search_read(  # type: ignore[attr-defined]
                "support.category", [("name", "ilike", category)], ["id", "name"], limit=1
            )
            if cats:
                vals["category_id"] = cats[0]["id"]
            else:
                out.warn(f"Category not found: {category}. Creating ticket without category.")

    try:
        ticket_id = c.create(_SUPPORT_MODEL, vals)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to create support ticket: {e}")
        raise typer.Exit(1) from e

    out.success(f"Created support ticket ID {ticket_id}: {subject}")
    if actx.json_mode:
        out.raw_json({"id": ticket_id, "name": subject, "priority": priority})


# ===================================================================
# CLOSE
# ===================================================================


@app.command("close")
def close(
    ctx: typer.Context,
    ticket_id: Annotated[int, typer.Argument(help="Ticket ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Close a support ticket (set status to resolved).

    Examples:
        kctl-odoo support close 42
        kctl-odoo support close 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _SUPPORT_MODEL):
        out.warn(_SUPPORT_HINT)
        return

    if not force and not typer.confirm(f"Close support ticket {ticket_id}?"):
        raise typer.Exit(0)

    try:
        c.write(_SUPPORT_MODEL, [ticket_id], {"state": "resolved"})  # type: ignore[attr-defined]
    except RPCError as e:
        # Try action method if direct write fails
        try:
            c.execute_kw(_SUPPORT_MODEL, "action_resolve", [[ticket_id]])  # type: ignore[attr-defined]
        except RPCError:
            try:
                c.execute_kw(_SUPPORT_MODEL, "action_close", [[ticket_id]])  # type: ignore[attr-defined]
            except RPCError:
                out.error(f"Failed to close support ticket {ticket_id}: {e}")
                raise typer.Exit(1) from None

    out.success(f"Support ticket {ticket_id} closed (resolved).")
    if actx.json_mode:
        out.raw_json({"id": ticket_id, "action": "closed", "status": "resolved"})


# ===================================================================
# SLA STATUS
# ===================================================================


@app.command("sla-status")
def sla_status(ctx: typer.Context) -> None:
    """Count tickets by SLA compliance (within/breached).

    Examples:
        kctl-odoo support sla-status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _SUPPORT_MODEL):
        out.warn(_SUPPORT_HINT)
        return

    from datetime import datetime

    now_str = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    try:
        total = c.search_count(_SUPPORT_MODEL, [])  # type: ignore[attr-defined]
        try:
            breached = c.search_count(  # type: ignore[attr-defined]
                _SUPPORT_MODEL,
                [
                    ("sla_deadline", "<", now_str),
                    ("sla_deadline", "!=", False),
                    ("state", "not in", ["resolved", "closed", "done"]),
                ],
            )
        except RPCError:
            # sla_deadline field may not exist — default to 0 breached
            breached = 0
        within = total - breached
    except RPCError as e:
        out.error(f"Failed to fetch SLA status: {e}")
        raise typer.Exit(1) from e

    rows = [
        ["Within SLA", str(within)],
        ["[red]Breached SLA[/red]", f"[red]{breached}[/red]"],
        ["[bold]Total[/bold]", f"[bold]{total}[/bold]"],
    ]
    json_data = {"total": total, "within_sla": within, "sla_breached": breached}

    out.table(
        "SLA Compliance",
        [("Status", "cyan"), ("Count", "")],
        rows,
        data_for_json=json_data,
    )
