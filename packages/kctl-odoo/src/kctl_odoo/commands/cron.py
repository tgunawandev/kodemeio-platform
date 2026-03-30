"""Scheduled action (ir.cron) management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.resolve import resolve_id

app = typer.Typer(help="Manage scheduled actions (ir.cron).")


@app.command("list")
def list_(
    ctx: typer.Context,
    active_only: Annotated[bool, typer.Option("--active/--all", help="Show only active crons")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """List scheduled actions."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if active_only:
        domain.append(("active", "=", True))

    crons = c.search_read(
        "ir.cron",
        domain=domain,
        fields=[
            "id",
            "name",
            "active",
            "interval_number",
            "interval_type",
            "nextcall",
            "lastcall",
            "model_id",
            "state",
        ],
        limit=limit,
        order="name",
    )

    rows = []
    json_data = []
    for cr in crons:
        status = "[green]active[/green]" if cr.get("active") else "[dim]inactive[/dim]"
        interval = f"{cr.get('interval_number', '')} {cr.get('interval_type', '')}"
        model = cr.get("model_id")
        model_name = model[1] if isinstance(model, list) else str(model or "")
        rows.append(
            [
                str(cr["id"]),
                cr["name"],
                status,
                interval,
                str(cr.get("nextcall", "")),
                str(cr.get("lastcall") or "-"),
            ]
        )
        json_data.append(
            {
                "id": cr["id"],
                "name": cr["name"],
                "active": cr.get("active"),
                "interval": interval,
                "model": model_name,
                "nextcall": cr.get("nextcall"),
                "lastcall": cr.get("lastcall"),
            }
        )

    out.table(
        f"Scheduled Actions ({len(crons)})",
        [("ID", "cyan"), ("Name", ""), ("Status", ""), ("Interval", ""), ("Next Call", ""), ("Last Call", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def enable(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Cron ID or name")],
) -> None:
    """Enable a scheduled action."""
    actx: AppContext = ctx.obj
    c = actx.client
    cron_id = resolve_id(c, "ir.cron", ilike=True, label="Cron", identifier=identifier)
    c.write("ir.cron", [cron_id], {"active": True})
    actx.output.success(f"Enabled cron {identifier}")


@app.command()
def disable(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Cron ID or name")],
) -> None:
    """Disable a scheduled action."""
    actx: AppContext = ctx.obj
    c = actx.client
    cron_id = resolve_id(c, "ir.cron", ilike=True, label="Cron", identifier=identifier)
    c.write("ir.cron", [cron_id], {"active": False})
    actx.output.success(f"Disabled cron {identifier}")


@app.command()
def run(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Cron ID or name")],
) -> None:
    """Run a scheduled action immediately."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cron_id = resolve_id(c, "ir.cron", ilike=True, label="Cron", identifier=identifier)
    out.info(f"Running cron {identifier} (ID: {cron_id})...")
    c.execute_kw("ir.cron", "method_direct_trigger", [[cron_id]])
    out.success(f"Cron {identifier} executed")


@app.command()
def history(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Cron ID or name")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Show execution history (trigger records) for a scheduled action."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cron_id = resolve_id(c, "ir.cron", ilike=True, label="Cron", identifier=identifier)

    # Read the cron name for display
    crons = c.read("ir.cron", [cron_id], fields=["id", "name"])
    cron_label = crons[0]["name"] if crons else str(cron_id)

    try:
        records = c.search_read(
            "ir.cron.trigger",
            domain=[("cron_id", "=", cron_id)],
            fields=["id", "cron_id", "call_at"],
            limit=limit,
            order="call_at desc",
        )
    except Exception:
        out.error("ir.cron.trigger model not available on this Odoo instance.")
        raise typer.Exit(1) from None

    if not records:
        out.info(f"No trigger history found for cron '{cron_label}' (ID: {cron_id}).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                str(r.get("call_at") or "-"),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "call_at": r.get("call_at"),
            }
        )

    out.table(
        f"Trigger History: {cron_label} ({len(records)})",
        [("ID", "cyan"), ("Call At", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def status(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 30,
) -> None:
    """Show active scheduled actions with overdue detection.

    Merged from: workers cron-status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    crons = c.search_read(
        "ir.cron",
        domain=[("active", "=", True)],
        fields=["id", "name", "interval_number", "interval_type", "nextcall", "lastcall", "model_id", "state"],
        limit=limit,
        order="nextcall",
    )

    if not crons:
        out.info("No active scheduled actions found.")
        if actx.json_mode:
            out.raw_json([])
        return

    now_str = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    json_data = []
    overdue_count = 0
    for cr in crons:
        interval = f"{cr.get('interval_number', '')} {cr.get('interval_type', '')}"
        nextcall = str(cr.get("nextcall", ""))
        lastcall = str(cr.get("lastcall") or "-")
        is_overdue = nextcall < now_str if nextcall else False
        if is_overdue:
            overdue_count += 1
        status_str = "[red]OVERDUE[/red]" if is_overdue else "[green]OK[/green]"
        model = cr.get("model_id")
        model_name = model[1] if isinstance(model, list) else str(model or "")

        rows.append(
            [
                str(cr["id"]),
                cr["name"][:40],
                interval,
                nextcall,
                lastcall,
                status_str,
            ]
        )
        json_data.append(
            {
                "id": cr["id"],
                "name": cr["name"],
                "interval": interval,
                "nextcall": cr.get("nextcall"),
                "lastcall": cr.get("lastcall"),
                "model": model_name,
                "overdue": is_overdue,
            }
        )

    title = f"Scheduled Actions ({len(crons)} active"
    if overdue_count:
        title += f", [red]{overdue_count} overdue[/red]"
    title += ")"

    out.table(
        title,
        [("ID", "cyan"), ("Name", ""), ("Interval", ""), ("Next Call", ""), ("Last Call", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def diagnose(
    ctx: typer.Context,
) -> None:
    """Check for failed or stuck cron jobs with detailed analysis.

    Merged from: troubleshoot cron-diagnostics
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    crons = c.search_read(
        "ir.cron",
        domain=[],
        fields=[
            "id",
            "name",
            "active",
            "interval_number",
            "interval_type",
            "lastcall",
            "nextcall",
            "priority",
        ],
        order="nextcall",
    )

    now = datetime.now(tz=UTC)
    rows = []
    json_data = []
    issues = 0

    for cr in crons:
        active = cr.get("active", False)
        active_str = "[green]active[/green]" if active else "[dim]inactive[/dim]"

        lastcall = cr.get("lastcall") or ""
        nextcall = cr.get("nextcall") or ""

        # Check for issues
        issue = ""
        if active and nextcall:
            try:
                next_dt = datetime.strptime(str(nextcall)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if next_dt < now - timedelta(hours=1):
                    issue = "[red]overdue[/red]"
                    issues += 1
            except (ValueError, TypeError):
                pass

        interval = f"{cr.get('interval_number', '')} {cr.get('interval_type', '')}"

        rows.append(
            [
                str(cr["id"]),
                cr["name"],
                active_str,
                interval,
                str(lastcall)[:19] if lastcall else "-",
                str(nextcall)[:19] if nextcall else "-",
                issue,
            ]
        )
        json_data.append(
            {
                "id": cr["id"],
                "name": cr["name"],
                "active": active,
                "interval": interval,
                "lastcall": lastcall,
                "nextcall": nextcall,
                "overdue": bool(issue),
            }
        )

    title = f"Cron Jobs ({len(crons)})"
    if issues:
        title += f" - [red]{issues} overdue[/red]"

    out.table(
        title,
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Status", ""),
            ("Interval", "dim"),
            ("Last Call", "dim"),
            ("Next Call", "dim"),
            ("Issue", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("create")
def create_cron(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Cron job name")],
    model: Annotated[str, typer.Option("--model", "-m", help="Model to call method on")] = "ir.cron",
    code: Annotated[str, typer.Option("--code", "-c", help="Python code to execute")] = "",
    interval: Annotated[int, typer.Option("--interval", help="Interval number")] = 1,
    interval_type: Annotated[
        str, typer.Option("--interval-type", help="Interval type: minutes/hours/days/weeks/months")
    ] = "days",
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active on creation")] = True,
) -> None:
    """Create a new scheduled action (ir.cron).

    Examples:
        kctl-odoo cron create "Daily Cleanup" --model ir.cron --code "env['auto.vacuum']._gc_transient_records()" --interval 1 --interval-type days
        kctl-odoo cron create "Hourly Sync" --code "env['base'].flush_all()" --interval 1 --interval-type hours
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    vals: dict = {
        "name": name,
        "model_id": None,
        "state": "code",
        "code": code or "# Add your Python code here",
        "interval_number": interval,
        "interval_type": interval_type,
        "active": active,
    }

    # Resolve model_id
    if model != "ir.cron":
        models = c.search_read("ir.model", domain=[("model", "=", model)], fields=["id"], limit=1)
        if models:
            vals["model_id"] = models[0]["id"]
        else:
            out.warn(f"Model '{model}' not found — creating with default model.")

    if not vals["model_id"]:
        models = c.search_read("ir.model", domain=[("model", "=", "ir.cron")], fields=["id"], limit=1)
        if models:
            vals["model_id"] = models[0]["id"]

    try:
        cron_id = c.execute_kw("ir.cron", "create", [vals])
        out.success(f"Created scheduled action: {name} (ID: {cron_id})")
        out.info(f"  Interval: every {interval} {interval_type}")
        out.info(f"  Active: {active}")
    except Exception as e:
        out.error(f"Failed to create cron: {e}")
        raise typer.Exit(1)
