"""Dunning/AR collection commands — cases, levels, follow-up."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="AR collection: dunning cases, follow-up, escalation.")

_DUNNING_MODEL = "dunning.case"
_DUNNING_HINT = "Dunning management module (dunning_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# CASES
# ===================================================================


@app.command("cases")
def cases(
    ctx: typer.Context,
    level: Annotated[str | None, typer.Option("--level", help="Filter by dunning level name (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List dunning cases.

    Examples:
        kctl-odoo dunning cases
        kctl-odoo dunning cases --level "Level 2" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DUNNING_MODEL):
        out.warn(_DUNNING_HINT)
        return

    domain: list = []
    if level:
        domain.append(("level_id.name", "ilike", level))

    preferred_fields = ["display_name", "partner_id", "level_id", "amount_overdue", "state", "date_dunning"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _DUNNING_MODEL,
            domain=domain,
            fields=preferred_fields,
            limit=limit,
            order="date_dunning desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _DUNNING_MODEL,
                domain=domain,
                fields=["display_name", "state", "create_date"],
                limit=limit,
                order="create_date desc",
            )
        except RPCError as e:
            out.error(f"Failed to list dunning cases: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No dunning cases found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        amount = r.get("amount_overdue", 0.0) or 0.0
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("partner_id")),
                _m2o_name(r.get("level_id")),
                f"{amount:,.2f}",
                str(r.get("state", "")),
                str(r.get("date_dunning", r.get("create_date", ""))),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "partner": _m2o_name(r.get("partner_id")),
                "level": _m2o_name(r.get("level_id")),
                "amount_overdue": amount,
                "state": r.get("state"),
                "date_dunning": r.get("date_dunning"),
            }
        )

    out.table(
        f"Dunning Cases ({len(records)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Partner", ""),
            ("Level", ""),
            ("Overdue", "red"),
            ("State", ""),
            ("Date", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LEVELS
# ===================================================================


@app.command("levels")
def levels(ctx: typer.Context) -> None:
    """List dunning levels with delay days and actions.

    Examples:
        kctl-odoo dunning levels
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DUNNING_MODEL):
        out.warn(_DUNNING_HINT)
        return

    preferred_fields = ["display_name", "sequence", "delay_days", "send_email", "send_letter", "block_order"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "dunning.level",
            domain=[],
            fields=preferred_fields,
            order="sequence asc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                "dunning.level",
                domain=[],
                fields=["display_name", "sequence"],
                order="sequence asc",
            )
        except RPCError as e:
            out.error(f"Failed to list dunning levels: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No dunning levels configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("sequence", "")),
                r.get("display_name", ""),
                str(r.get("delay_days", "")),
                "Y" if r.get("send_email") else "-",
                "Y" if r.get("send_letter") else "-",
                "Y" if r.get("block_order") else "-",
            ]
        )
        json_data.append(
            {
                "sequence": r.get("sequence"),
                "display_name": r.get("display_name"),
                "delay_days": r.get("delay_days"),
                "send_email": r.get("send_email"),
                "send_letter": r.get("send_letter"),
                "block_order": r.get("block_order"),
            }
        )

    out.table(
        "Dunning Levels",
        [("Seq", "dim"), ("Name", "cyan"), ("Delay Days", ""), ("Email", ""), ("Letter", ""), ("Block Orders", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# RUN
# ===================================================================


@app.command("run")
def run(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate without creating/updating cases")] = False,
) -> None:
    """Trigger dunning evaluation: create or escalate overdue cases.

    Examples:
        kctl-odoo dunning run --dry-run
        kctl-odoo dunning run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DUNNING_MODEL):
        out.warn(_DUNNING_HINT)
        return

    if dry_run:
        out.info("[dry-run] Dunning evaluation would run now. Use without --dry-run to execute.")
        if actx.json_mode:
            out.raw_json({"dry_run": True, "action": "dunning_run"})
        return

    try:
        c.execute_kw("dunning.case", "run_dunning", [[]])  # type: ignore[attr-defined]
        out.success("Dunning evaluation triggered successfully.")
    except RPCError as e:
        out.warn(f"Could not trigger dunning run via execute_kw: {e}")
        out.info("To run dunning manually: Accounting → Dunning → Run Dunning")

    if actx.json_mode:
        out.raw_json({"action": "dunning_run", "dry_run": False})


# ===================================================================
# STATS
# ===================================================================


@app.command("stats")
def stats(ctx: typer.Context) -> None:
    """Dunning statistics: cases by level and total overdue amount.

    Examples:
        kctl-odoo dunning stats
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DUNNING_MODEL):
        out.warn(_DUNNING_HINT)
        return

    try:
        total = c.search_count(_DUNNING_MODEL, [])
    except RPCError as e:
        out.error(f"Failed to fetch dunning stats: {e}")
        raise typer.Exit(1) from e

    if total == 0:
        out.info("No dunning cases found.")
        if actx.json_mode:
            out.raw_json({"total": 0})
        return

    # Count by state since read_group is not available via JSON-RPC
    rows = []
    json_data = []
    for state_val, state_label in [("draft", "Draft"), ("open", "Open"), ("done", "Done"), ("cancel", "Cancelled")]:
        try:
            count = c.search_count(_DUNNING_MODEL, [("state", "=", state_val)])
        except (RPCError, Exception):
            count = 0
        if count > 0:
            rows.append([state_label, str(count)])
        json_data.append({"state": state_label, "count": count})

    rows.append(["[bold]TOTAL[/bold]", f"[bold]{total}[/bold]"])

    out.table(
        "Dunning Statistics",
        [("State", "cyan"), ("Cases", "")],
        rows,
        data_for_json={"states": json_data, "total": total},
    )
