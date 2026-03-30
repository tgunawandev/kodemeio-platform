"""Audit trail commands — view and manage OCA auditlog records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Audit trail: view and manage auditlog records.")

_AUDIT_MODEL = "auditlog.log"
_AUDIT_HINT = "OCA auditlog module is not installed. Install auditlog to enable audit trail."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_logs(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", help="Filter by model name (ilike)")] = None,
    user: Annotated[str | None, typer.Option("--user", help="Filter by user name (ilike)")] = None,
    days: Annotated[int, typer.Option("--days", help="Logs from last N days")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List audit log entries.

    Examples:
        kctl-odoo audit list
        kctl-odoo audit list --model res.partner --days 7
        kctl-odoo audit list --user admin --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _AUDIT_MODEL):
        out.warn(_AUDIT_HINT)
        return

    since = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    domain: list = [("create_date", ">=", since)]
    if model:
        domain.append(("model_id.model", "ilike", model))
    if user:
        domain.append(("user_id.name", "ilike", user))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _AUDIT_MODEL,
            domain=domain,
            fields=["name", "model_id", "res_id", "method", "user_id", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list audit logs: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No audit log entries found.")
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
                _m2o_name(r.get("model_id")),
                str(r.get("res_id", "")),
                str(r.get("method", "")),
                _m2o_name(r.get("user_id")),
                str(r.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "model": _m2o_name(r.get("model_id")),
                "res_id": r.get("res_id"),
                "method": r.get("method"),
                "user": _m2o_name(r.get("user_id")),
                "create_date": r.get("create_date"),
            }
        )

    out.table(
        f"Audit Logs ({len(records)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("Rec ID", "dim"),
            ("Method", ""),
            ("User", ""),
            ("Date", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# DETAIL
# ===================================================================


@app.command("detail")
def detail(
    ctx: typer.Context,
    log_id: Annotated[int, typer.Argument(help="Audit log ID")],
) -> None:
    """Show detail of an audit log entry including field changes.

    Examples:
        kctl-odoo audit detail 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _AUDIT_MODEL):
        out.warn(_AUDIT_HINT)
        return

    try:
        records = c.read(  # type: ignore[attr-defined]
            _AUDIT_MODEL,
            [log_id],
            ["name", "model_id", "res_id", "method", "user_id", "create_date", "line_ids"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch audit log {log_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Audit log not found: {log_id}")
        raise typer.Exit(1)

    rec = records[0]
    sections = [
        (
            "Audit Log",
            [
                ("ID", str(rec["id"])),
                ("Name", rec.get("name", "")),
                ("Model", _m2o_name(rec.get("model_id"))),
                ("Record ID", str(rec.get("res_id", ""))),
                ("Method", str(rec.get("method", ""))),
                ("User", _m2o_name(rec.get("user_id"))),
                ("Date", str(rec.get("create_date", ""))),
            ],
        )
    ]

    json_result: dict = {
        "id": rec["id"],
        "name": rec.get("name"),
        "model": _m2o_name(rec.get("model_id")),
        "res_id": rec.get("res_id"),
        "method": rec.get("method"),
        "user": _m2o_name(rec.get("user_id")),
        "create_date": rec.get("create_date"),
        "lines": [],
    }

    out.detail("Audit Log Detail", sections, data_for_json=json_result)

    line_ids = rec.get("line_ids", [])
    if line_ids:
        try:
            lines = c.read(  # type: ignore[attr-defined]
                "auditlog.log.line",
                line_ids,
                ["field_id", "field_description", "old_value_text", "new_value_text"],
            )
        except RPCError as e:
            out.warn(f"Failed to read audit lines: {e}")
            return

        rows = []
        lines_json = []
        for ln in lines:
            field = _m2o_name(ln.get("field_id")) or str(ln.get("field_description", ""))
            old_val = str(ln.get("old_value_text") or "")[:60]
            new_val = str(ln.get("new_value_text") or "")[:60]
            rows.append([field, old_val, new_val])
            lines_json.append(
                {"field": field, "old_value": ln.get("old_value_text"), "new_value": ln.get("new_value_text")}
            )

        json_result["lines"] = lines_json

        out.table(
            f"Field Changes ({len(lines)})",
            [("Field", "cyan"), ("Old Value", "red"), ("New Value", "green")],
            rows,
            data_for_json=lines_json,
        )


# ===================================================================
# RULES
# ===================================================================


@app.command("rules")
def rules(ctx: typer.Context) -> None:
    """List auditlog rules (which models are tracked).

    Examples:
        kctl-odoo audit rules
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _AUDIT_MODEL):
        out.warn(_AUDIT_HINT)
        return

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "auditlog.rule",
            domain=[],
            fields=["name", "model_id", "log_read", "log_write", "log_create", "log_unlink", "state"],
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list auditlog rules: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No auditlog rules configured.")
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
                _m2o_name(r.get("model_id")),
                "Y" if r.get("log_read") else "-",
                "Y" if r.get("log_write") else "-",
                "Y" if r.get("log_create") else "-",
                "Y" if r.get("log_unlink") else "-",
                str(r.get("state", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "model": _m2o_name(r.get("model_id")),
                "log_read": r.get("log_read"),
                "log_write": r.get("log_write"),
                "log_create": r.get("log_create"),
                "log_unlink": r.get("log_unlink"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Auditlog Rules ({len(records)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("Read", ""),
            ("Write", ""),
            ("Create", ""),
            ("Unlink", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CLEANUP
# ===================================================================


@app.command("cleanup")
def cleanup(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Delete logs older than N days")] = 90,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Count only, do not delete")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete old audit log entries.

    Examples:
        kctl-odoo audit cleanup --days 90 --dry-run
        kctl-odoo audit cleanup --days 30 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _AUDIT_MODEL):
        out.warn(_AUDIT_HINT)
        return

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    domain = [("create_date", "<", cutoff)]

    try:
        count = c.search_count(_AUDIT_MODEL, domain)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to count audit logs: {e}")
        raise typer.Exit(1) from e

    out.info(f"Found {count} audit log(s) older than {days} days (before {cutoff}).")

    if dry_run:
        out.info("[dry-run] No records deleted.")
        if actx.json_mode:
            out.raw_json({"count": count, "deleted": 0, "dry_run": True})
        return

    if count == 0:
        if actx.json_mode:
            out.raw_json({"count": 0, "deleted": 0})
        return

    if not force and not typer.confirm(f"Delete {count} audit log entries?"):
        raise typer.Exit(0)

    try:
        ids = c.search(_AUDIT_MODEL, domain, limit=0)  # type: ignore[attr-defined]
        c.unlink(_AUDIT_MODEL, ids)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to delete audit logs: {e}")
        raise typer.Exit(1) from e

    out.success(f"Deleted {count} audit log entries older than {days} days.")
    if actx.json_mode:
        out.raw_json({"count": count, "deleted": count})
