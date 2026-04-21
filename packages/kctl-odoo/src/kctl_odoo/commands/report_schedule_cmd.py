"""Report schedule CRUD and execution.

Wraps the ``report.schedule`` model shipped with ``report_management``.
Lets operators create, manage, and trigger scheduled report generation
from the CLI without needing the Odoo UI.

Mounted under ``kctl-odoo report schedule``.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report schedule: create/manage scheduled report delivery via CLI.")


_WRITABLE_FIELDS = (
    "name",
    "active",
    "template_id",
    "frequency",
    "day_of_week",
    "day_of_month",
    "time_of_day",
    "date_range_mode",
    "custom_date_from",
    "custom_date_to",
    "company_id",
    "target_move",
    "comparison_mode",
    "export_format",
    "recipient_user_ids",
    "recipient_partner_ids",
)

_LIST_FIELDS = (
    "id",
    "name",
    "template_id",
    "frequency",
    "date_range_mode",
    "export_format",
    "next_run",
    "last_run",
    "run_count",
    "active",
)

_SHOW_FIELDS = (
    "id",
    "name",
    "active",
    "template_id",
    "frequency",
    "day_of_week",
    "day_of_month",
    "time_of_day",
    "next_run",
    "last_run",
    "last_instance_id",
    "run_count",
    "recipient_user_ids",
    "recipient_partner_ids",
    "date_range_mode",
    "custom_date_from",
    "custom_date_to",
    "company_id",
    "target_move",
    "comparison_mode",
    "export_format",
)

_HISTORY_FIELDS = (
    "id",
    "name",
    "state",
    "date_from",
    "date_to",
    "create_date",
    "export_format",
    "company_id",
)


def _require_report_management(c, out) -> bool:
    if not model_available(c, "report.schedule"):
        out.warn("report.schedule model not available. Install with: kctl-odoo modules install report_management")
        return False
    return True


def _resolve_schedule(c, id_or_name: str) -> int | None:
    """Resolve a schedule by numeric id or by name substring."""
    if id_or_name.isdigit():
        ids = c.search("report.schedule", [("id", "=", int(id_or_name))], limit=1)
        return ids[0] if ids else None
    ids = c.search("report.schedule", [("name", "ilike", id_or_name)], limit=1)
    return ids[0] if ids else None


def _resolve_template_id(c, template_code: str) -> int | None:
    """Resolve a template code to a report.template id."""
    ids = c.search("report.template", [("code", "=", template_code)], limit=1)
    return ids[0] if ids else None


def _resolve_user_logins(c, logins: list[str]) -> list[int]:
    """Resolve a list of res.users login names to user ids."""
    if not logins:
        return []
    user_ids = []
    for login in logins:
        ids = c.search("res.users", [("login", "=", login)], limit=1)
        if not ids:
            raise typer.BadParameter(f"User not found with login: {login!r}")
        user_ids.append(ids[0])
    return user_ids


def _parse_kv(pairs: list[str] | None) -> dict:
    """Parse ``--set key=value`` options into a dict. JSON-decodes values when possible."""
    out: dict = {}
    if not pairs:
        return out
    for raw in pairs:
        if "=" not in raw:
            raise typer.BadParameter(f"Expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        if key not in _WRITABLE_FIELDS:
            raise typer.BadParameter(f"Unknown field {key!r}. Writable fields: {', '.join(_WRITABLE_FIELDS)}")
        val = val.strip()
        try:
            out[key] = json.loads(val)
        except ValueError:
            out[key] = val
    return out


def _format_m2o(val) -> str:
    """Format a Many2one RPC value [id, name] or False to a display string."""
    if isinstance(val, list) and len(val) == 2:
        return str(val[1])
    return "-"


def _format_datetime(val) -> str:
    """Format a datetime string or False."""
    if val:
        return str(val)[:19]
    return "-"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command("list")
def list_schedules(
    ctx: typer.Context,
    active_only: Annotated[
        bool,
        typer.Option("--active-only/--all", help="Show only active schedules (default) or all"),
    ] = True,
    frequency: Annotated[
        str | None,
        typer.Option("--frequency", "-f", help="Filter by frequency (daily/weekly/monthly/quarterly)"),
    ] = None,
) -> None:
    """List all report schedules on the connected tenant."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    domain: list = []
    if active_only:
        domain.append(("active", "=", True))
    if frequency:
        domain.append(("frequency", "=", frequency))

    rows = c.search_read(
        "report.schedule",
        domain=domain,
        fields=list(_LIST_FIELDS),
        order="next_run, name",
    )
    if not rows:
        out.info("No report schedules found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            (r.get("name") or "")[:40],
            _format_m2o(r.get("template_id")),
            r.get("frequency") or "-",
            r.get("date_range_mode") or "-",
            r.get("export_format") or "-",
            _format_datetime(r.get("next_run")),
            _format_datetime(r.get("last_run")),
            str(r.get("run_count") or 0),
            "Y" if r.get("active") else "N",
        ]
        for r in rows
    ]
    out.table(
        f"Report Schedules ({len(rows)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Template", ""),
            ("Freq", ""),
            ("Range", ""),
            ("Format", ""),
            ("Next Run", ""),
            ("Last Run", "dim"),
            ("Runs", "dim"),
            ("Act", ""),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_schedule(
    ctx: typer.Context,
    id_or_name: Annotated[str, typer.Argument(help="Schedule id or name substring")],
) -> None:
    """Show one schedule in detail (all fields as JSON)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    schedule_id = _resolve_schedule(c, id_or_name)
    if schedule_id is None:
        out.error(f"Schedule not found: {id_or_name}")
        raise typer.Exit(1)

    (rec,) = c.read("report.schedule", [schedule_id], list(_SHOW_FIELDS))
    if actx.json_mode:
        out.raw_json(rec)
        return
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command("create")
def create_schedule(
    ctx: typer.Context,
    template_code: Annotated[str, typer.Argument(help="Template code to schedule (resolved via report.template)")],
    frequency: Annotated[str, typer.Argument(help="Frequency: daily / weekly / monthly / quarterly")],
    day_of_week: Annotated[
        str | None,
        typer.Option("--day-of-week", help="Day of week for weekly: 0=Mon .. 6=Sun"),
    ] = None,
    day_of_month: Annotated[
        int | None,
        typer.Option("--day-of-month", help="Day of month for monthly/quarterly (1-28)"),
    ] = None,
    time: Annotated[
        float,
        typer.Option("--time", "-t", help="Time of day as float (e.g. 8.0 = 08:00, 14.5 = 14:30)"),
    ] = 8.0,
    date_range: Annotated[
        str,
        typer.Option("--date-range", help="Date range mode: previous_month/previous_week/previous_quarter/ytd/custom"),
    ] = "previous_month",
    export_format: Annotated[
        str,
        typer.Option("--export-format", help="Export format: pdf / xlsx / both"),
    ] = "pdf",
    target_move: Annotated[
        str,
        typer.Option("--target-move", help="Target move: posted / all"),
    ] = "posted",
    comparison: Annotated[
        str,
        typer.Option("--comparison", help="Comparison mode: none / previous_year / previous_period"),
    ] = "none",
    recipient_user: Annotated[
        list[str] | None,
        typer.Option("--recipient-user", "-u", help="Recipient user login (repeatable)"),
    ] = None,
    recipient_partner: Annotated[
        list[int] | None,
        typer.Option("--recipient-partner", "-p", help="Recipient partner id (repeatable)"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Override auto-generated schedule name"),
    ] = None,
) -> None:
    """Create a new report schedule.

    At least one recipient (--recipient-user or --recipient-partner) is required.

    Examples:

    \b
        kctl-odoo report schedule create pnl monthly \\
            --recipient-user admin --export-format pdf

    \b
        kctl-odoo report schedule create balance_sheet quarterly \\
            --day-of-month 15 --time 9.0 \\
            --recipient-user admin --recipient-user cfo \\
            --comparison previous_year
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    # Resolve template
    template_id = _resolve_template_id(c, template_code)
    if template_id is None:
        out.error(f"Template not found with code: {template_code!r}")
        raise typer.Exit(1)

    # Resolve recipients
    user_ids = _resolve_user_logins(c, recipient_user or [])
    partner_ids = recipient_partner or []

    if not user_ids and not partner_ids:
        out.error("At least one recipient is required. Use --recipient-user or --recipient-partner.")
        raise typer.Exit(1)

    # Validate frequency
    if frequency not in ("daily", "weekly", "monthly", "quarterly"):
        out.error(f"Invalid frequency: {frequency!r}. Must be daily/weekly/monthly/quarterly.")
        raise typer.Exit(1)

    vals: dict = {
        "template_id": template_id,
        "frequency": frequency,
        "time_of_day": time,
        "date_range_mode": date_range,
        "export_format": export_format,
        "target_move": target_move,
        "comparison_mode": comparison,
        "recipient_user_ids": [(6, 0, user_ids)],
        "recipient_partner_ids": [(6, 0, partner_ids)],
    }
    if name:
        vals["name"] = name
    if day_of_week is not None:
        vals["day_of_week"] = day_of_week
    if day_of_month is not None:
        vals["day_of_month"] = day_of_month

    try:
        res = c.execute_kw("report.schedule", "create", [vals])
    except RPCError as exc:
        out.error(f"Create failed: {exc}")
        raise typer.Exit(1) from exc

    new_id = res[0] if isinstance(res, list) else res
    out.success(f"Created report.schedule id={new_id} template={template_code!r} frequency={frequency}")
    if actx.json_mode:
        out.raw_json({"id": new_id, "template_code": template_code, "frequency": frequency})


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command("update")
def update_schedule(
    ctx: typer.Context,
    schedule_id: Annotated[int, typer.Argument(help="Schedule id to update")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable). See `show` for writable fields."),
    ],
) -> None:
    """Update fields on a report schedule.

    Examples:

    \b
        kctl-odoo report schedule update 5 --set frequency=weekly --set day_of_week=0
        kctl-odoo report schedule update 12 --set active=false
        kctl-odoo report schedule update 3 --set time_of_day=14.5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    ids = c.search("report.schedule", [("id", "=", schedule_id)], limit=1)
    if not ids:
        out.error(f"Schedule not found: id={schedule_id}")
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to update -- pass at least one --set key=value.")
        raise typer.Exit(1)

    try:
        c.execute_kw("report.schedule", "write", [[schedule_id], vals])
    except RPCError as exc:
        out.error(f"Update failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Updated report.schedule id={schedule_id}: {', '.join(vals.keys())}")
    if actx.json_mode:
        out.raw_json({"id": schedule_id, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_schedule(
    ctx: typer.Context,
    schedule_id: Annotated[int, typer.Argument(help="Schedule id to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a report schedule by id.

    Running instances are not affected -- only the schedule record is removed.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    recs = c.search_read("report.schedule", [("id", "=", schedule_id)], fields=["id", "name"], limit=1)
    if not recs:
        out.error(f"Schedule not found: id={schedule_id}")
        raise typer.Exit(1)

    sched_name = recs[0].get("name") or f"id={schedule_id}"

    if not yes and not typer.confirm(f"Delete report schedule {sched_name!r}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("report.schedule", "unlink", [[schedule_id]])
    except RPCError as exc:
        out.error(f"Delete failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Deleted report.schedule {sched_name!r} id={schedule_id}")
    if actx.json_mode:
        out.raw_json({"id": schedule_id, "name": sched_name, "deleted": True})


# ---------------------------------------------------------------------------
# run-now
# ---------------------------------------------------------------------------
@app.command("run-now")
def run_now(
    ctx: typer.Context,
    schedule_id: Annotated[int, typer.Argument(help="Schedule id to execute immediately")],
) -> None:
    """Trigger immediate execution of a schedule.

    Calls the server-side ``action_run_now`` method which generates
    a report instance and sends it to all configured recipients.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    ids = c.search("report.schedule", [("id", "=", schedule_id)], limit=1)
    if not ids:
        out.error(f"Schedule not found: id={schedule_id}")
        raise typer.Exit(1)

    try:
        result = c.execute_kw("report.schedule", "action_run_now", [[schedule_id]])
    except RPCError as exc:
        out.error(f"Run failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Triggered immediate execution for schedule id={schedule_id}")
    if actx.json_mode:
        out.raw_json({"id": schedule_id, "result": result})


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
@app.command("history")
def history(
    ctx: typer.Context,
    schedule_id: Annotated[int, typer.Argument(help="Schedule id to show history for")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of recent instances to show"),
    ] = 10,
) -> None:
    """Show run history (recent instances) for a schedule."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    ids = c.search("report.schedule", [("id", "=", schedule_id)], limit=1)
    if not ids:
        out.error(f"Schedule not found: id={schedule_id}")
        raise typer.Exit(1)

    # report.instance records linked to this schedule
    instances = c.search_read(
        "report.instance",
        domain=[("schedule_id", "=", schedule_id)],
        fields=list(_HISTORY_FIELDS),
        order="create_date desc",
        limit=limit,
    )
    if not instances:
        out.info(f"No run history for schedule id={schedule_id}.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            (r.get("name") or "")[:36],
            r.get("state") or "-",
            str(r.get("date_from") or "-"),
            str(r.get("date_to") or "-"),
            _format_datetime(r.get("create_date")),
            r.get("export_format") or "-",
            _format_m2o(r.get("company_id")),
        ]
        for r in instances
    ]
    out.table(
        f"Run History for Schedule #{schedule_id} ({len(instances)} instances)",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("State", ""),
            ("Date From", ""),
            ("Date To", ""),
            ("Created", "dim"),
            ("Format", ""),
            ("Company", "dim"),
        ],
        table_rows,
        data_for_json=instances,
    )
