"""SQL Export CRUD and execution.

Wraps the OCA ``sql.export`` model — define SQL queries in Odoo,
execute them, and download results as CSV/XLSX. Lets operators
manage ad-hoc data extractions via CLI without the web UI.

Mounted under ``kctl-odoo sql-export``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="SQL Export: create, validate, execute, and download ad-hoc SQL queries.")

_MODEL = "sql.export"

_LIST_FIELDS = [
    "id",
    "name",
    "state",
    "file_format",
    "encoding",
    "last_execution_date",
    "last_execution_uid",
]

_DETAIL_FIELDS = _LIST_FIELDS + [
    "query",
    "copy_options",
    "group_ids",
    "user_ids",
    "use_properties",
    "query_properties_definition",
    "note",
]


def _check_module(c: object, out: object) -> bool:
    if not model_available(c, _MODEL):
        out.error("sql_export module is not installed on this instance.")
        raise typer.Exit(1)
    return True


def _m2o(val: object) -> str:
    if isinstance(val, list) and len(val) == 2:
        return f"{val[1]} (id={val[0]})"
    if isinstance(val, (int, str)):
        return str(val)
    return str(val) if val else ""


@app.command("list")
def list_(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help="Filter by state: draft or sql_valid")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 50,
) -> None:
    """List SQL export queries.

    Examples:
        kctl-odoo sql-export list
        kctl-odoo sql-export list --state sql_valid
        kctl-odoo sql-export list --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(_MODEL, domain, _LIST_FIELDS, limit=limit, order="id")
    except RPCError as e:
        out.error(f"Failed to list: {e.detail}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json(records)
        return

    if not records:
        out.info("No SQL exports found.")
        return

    out.info(f"{'ID':>5s}  {'State':<10s}  {'Format':<6s}  {'Last Run':<20s}  {'Name'}")
    out.info("─" * 80)
    for r in records:
        last = str(r.get("last_execution_date") or "—")[:19]
        out.info(
            f"{r['id']:>5d}  {r.get('state', ''):<10s}  {r.get('file_format', ''):<6s}  {last:<20s}  {r.get('name', '')}"
        )
    out.info(f"  {len(records)} exports")


@app.command("show")
def show(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
) -> None:
    """Show SQL export details including query and parameters.

    Examples:
        kctl-odoo sql-export show 1
        kctl-odoo sql-export show 1 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    try:
        records = c.search_read(_MODEL, [("id", "=", export_id)], _DETAIL_FIELDS, limit=1)
    except RPCError as e:
        out.error(f"Failed to read: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"SQL export not found: {export_id}")
        raise typer.Exit(1)

    r = records[0]

    if actx.json_mode:
        out.raw_json(r)
        return

    out.info(f"SQL Export #{r['id']}: {r.get('name', '')}")
    out.info(f"  State:     {r.get('state', '')}")
    out.info(f"  Format:    {r.get('file_format', '')}")
    out.info(f"  Encoding:  {r.get('encoding', '')}")
    out.info(f"  Options:   {r.get('copy_options', '')}")
    out.info(f"  Last Run:  {r.get('last_execution_date') or '—'}")
    out.info(f"  Last User: {_m2o(r.get('last_execution_uid'))}")
    out.info(f"  Groups:    {r.get('group_ids') or '—'}")
    out.info(f"  Users:     {r.get('user_ids') or '—'}")
    if r.get("query_properties_definition"):
        out.info(f"  Params:    {json.dumps(r['query_properties_definition'], indent=2)}")
    out.info(f"\n  Query:\n  {'-' * 60}")
    for line in (r.get("query") or "").strip().split("\n"):
        out.info(f"  {line}")
    out.info(f"  {'-' * 60}")


@app.command("create")
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Export name")],
    query: Annotated[str, typer.Option("--query", "-q", help="SQL query text")],
    file_format: Annotated[str, typer.Option("--format", "-f", help="Output format: csv or excel")] = "csv",
    encoding: Annotated[str, typer.Option("--encoding", help="File encoding")] = "utf-8",
    copy_options: Annotated[
        str, typer.Option("--copy-options", help="PostgreSQL COPY options")
    ] = "CSV HEADER DELIMITER ';'",
    validate: Annotated[bool, typer.Option("--validate/--no-validate", help="Auto-validate after creation")] = True,
) -> None:
    """Create a new SQL export query.

    Examples:
        kctl-odoo sql-export create "Revenue by Month" -q "SELECT date_trunc('month', date) as month, SUM(amount_total) FROM account_move WHERE state='posted' GROUP BY 1 ORDER BY 1"
        kctl-odoo sql-export create "Partners" -q "SELECT name, email FROM res_partner WHERE active" -f excel
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    vals = {
        "name": name,
        "query": query,
        "file_format": file_format,
        "encoding": encoding,
        "copy_options": copy_options,
    }

    try:
        export_id = c.execute_kw(_MODEL, "create", [vals])
    except RPCError as e:
        out.error(f"Failed to create: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Created SQL export #{export_id}: {name}")

    if validate:
        try:
            c.execute_kw(_MODEL, "button_validate_sql_expression", [[export_id]])
            out.success("SQL validated successfully.")
        except RPCError as e:
            out.warning(f"Validation failed: {e.detail}")
            out.info(f"Export created in draft state. Fix the query and run: kctl-odoo sql-export validate {export_id}")

    if actx.json_mode:
        out.raw_json({"id": export_id, "name": name, "state": "sql_valid" if validate else "draft"})


@app.command("update")
def update(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    query: Annotated[str | None, typer.Option("--query", "-q", help="New SQL query")] = None,
    file_format: Annotated[str | None, typer.Option("--format", "-f", help="csv or excel")] = None,
    encoding: Annotated[str | None, typer.Option("--encoding")] = None,
    copy_options: Annotated[str | None, typer.Option("--copy-options")] = None,
    validate: Annotated[bool, typer.Option("--validate/--no-validate", help="Auto-validate after update")] = True,
) -> None:
    """Update an existing SQL export.

    Resets state to draft, applies changes, then re-validates.

    Examples:
        kctl-odoo sql-export update 1 -q "SELECT id, name FROM res_partner LIMIT 10"
        kctl-odoo sql-export update 1 --name "Updated Export" --format excel
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    vals: dict = {}
    if name is not None:
        vals["name"] = name
    if query is not None:
        vals["query"] = query
    if file_format is not None:
        vals["file_format"] = file_format
    if encoding is not None:
        vals["encoding"] = encoding
    if copy_options is not None:
        vals["copy_options"] = copy_options

    if not vals:
        out.error("No fields to update. Use --name, --query, --format, --encoding, or --copy-options.")
        raise typer.Exit(1)

    try:
        c.execute_kw(_MODEL, "button_set_draft", [[export_id]])
        c.execute_kw(_MODEL, "write", [[export_id], vals])
    except RPCError as e:
        out.error(f"Failed to update: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Updated SQL export #{export_id}")

    if validate and "query" in vals:
        try:
            c.execute_kw(_MODEL, "button_validate_sql_expression", [[export_id]])
            out.success("SQL re-validated successfully.")
        except RPCError as e:
            out.warning(f"Validation failed: {e.detail}")


@app.command("delete")
def delete(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a SQL export.

    Examples:
        kctl-odoo sql-export delete 5
        kctl-odoo sql-export delete 5 -y
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    try:
        records = c.search_read(_MODEL, [("id", "=", export_id)], ["id", "name"], limit=1)
    except RPCError as e:
        out.error(f"Failed to read: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"SQL export not found: {export_id}")
        raise typer.Exit(1)

    name = records[0].get("name", "")
    if not force and not typer.confirm(f"Delete SQL export #{export_id} '{name}'?"):
        raise typer.Exit(0)

    try:
        c.execute_kw(_MODEL, "unlink", [[export_id]])
    except RPCError as e:
        out.error(f"Failed to delete: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Deleted SQL export #{export_id}: {name}")


@app.command("validate")
def validate_cmd(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
) -> None:
    """Validate SQL query (draft -> sql_valid).

    Examples:
        kctl-odoo sql-export validate 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    try:
        c.execute_kw(_MODEL, "button_validate_sql_expression", [[export_id]])
    except RPCError as e:
        out.error(f"Validation failed: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"SQL export #{export_id} validated successfully.")


def _parse_params(params: list[str] | None) -> dict:
    if not params:
        return {}
    result = {}
    for p in params:
        if "=" not in p:
            raise typer.BadParameter(f"Invalid param format: {p!r} (expected key=value)")
        k, v = p.split("=", 1)
        result[k.strip()] = v.strip()
    return result


@app.command("execute")
def execute(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
    params: Annotated[list[str] | None, typer.Option("--param", "-p", help="Query parameter key=value")] = None,
) -> None:
    """Execute a SQL export and download the result file.

    Examples:
        kctl-odoo sql-export execute 1
        kctl-odoo sql-export execute 1 -o revenue.csv
        kctl-odoo sql-export execute 1 -p company_id=42 -p year=2026
    """
    import base64
    import re

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    variable_dict = _parse_params(params)

    try:
        records = c.search_read(
            _MODEL, [("id", "=", export_id)], ["name", "state", "file_format", "use_properties"], limit=1
        )
    except RPCError as e:
        out.error(f"Failed to read: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"SQL export not found: {export_id}")
        raise typer.Exit(1)

    rec = records[0]
    if rec["state"] != "sql_valid":
        out.error(f"SQL export #{export_id} is in draft state. Run: kctl-odoo sql-export validate {export_id}")
        raise typer.Exit(1)

    ext = "xlsx" if rec.get("file_format") == "excel" else "csv"

    try:
        result = c.execute_kw(_MODEL, "export_sql_query", [[export_id]])
    except RPCError as e:
        out.error(f"Execution failed: {e.detail}")
        raise typer.Exit(1) from e

    wiz_id_from_url = None
    if isinstance(result, dict) and result.get("type") == "ir.actions.act_url":
        url = result.get("url", "")
        m = re.search(r"id=(\d+)", url)
        if m:
            wiz_id_from_url = int(m.group(1))
    elif isinstance(result, dict) and result.get("type") == "ir.actions.act_window":
        wiz_id_from_url = result.get("res_id")

    if wiz_id_from_url:
        try:
            wiz_data = c.search_read(
                "sql.file.wizard",
                [("id", "=", wiz_id_from_url)],
                ["binary_file"],
                limit=1,
            )
            if wiz_data and wiz_data[0].get("binary_file"):
                file_bytes = base64.b64decode(wiz_data[0]["binary_file"])
                out_path = output or f"{rec['name'].replace(' ', '_')}_{export_id}.{ext}"
                Path(out_path).write_bytes(file_bytes)
                out.success(f"Downloaded: {out_path} ({len(file_bytes):,} bytes)")
                return
        except RPCError as e:
            out.warning(f"Could not download file: {e.detail}")

    out.warning("Export triggered but file could not be downloaded via CLI.")
    out.info("Open Odoo UI to download the file.")
    if actx.json_mode:
        out.raw_json({"id": export_id, "result": result})


@app.command("preview")
def preview(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max rows to show")] = 20,
    params: Annotated[list[str] | None, typer.Option("--param", "-p", help="Query parameter key=value")] = None,
) -> None:
    """Preview SQL export results in terminal (first N rows).

    Examples:
        kctl-odoo sql-export preview 1
        kctl-odoo sql-export preview 1 --limit 50
        kctl-odoo sql-export preview 1 -p company_id=42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    try:
        records = c.search_read(_MODEL, [("id", "=", export_id)], ["name", "state", "query"], limit=1)
    except RPCError as e:
        out.error(f"Failed to read: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"SQL export not found: {export_id}")
        raise typer.Exit(1)

    rec = records[0]
    if rec["state"] != "sql_valid":
        out.error(f"SQL export #{export_id} is in draft state. Validate first.")
        raise typer.Exit(1)

    variable_dict = _parse_params(params)

    try:
        result = c.execute_kw(
            _MODEL,
            "_execute_sql_request",
            [[export_id], variable_dict, "fetchall", True, None, None, True],
        )
    except RPCError as e:
        out.error(f"Preview failed: {e.detail}")
        out.info("Tip: The query may need parameters. Use -p key=value")
        raise typer.Exit(1) from e

    if not result:
        out.info("Query returned no rows.")
        return

    if actx.json_mode:
        out.raw_json({"id": export_id, "name": rec["name"], "rows": result[:limit]})
        return

    if isinstance(result[0], (list, tuple)):
        header = list(result[0]) if isinstance(result[0][0], str) else [f"col_{i}" for i in range(len(result[0]))]
        data_rows = result[1 : limit + 1] if isinstance(result[0][0], str) else result[:limit]

        col_widths = [
            min(max(len(str(h)), max((len(str(r[i] if i < len(r) else "")) for r in data_rows), default=4)), 30)
            for i, h in enumerate(header)
        ]

        hdr_line = "  ".join(f"{str(h):<{w}s}" for h, w in zip(header, col_widths))
        out.info(f"  {hdr_line}")
        out.info(f"  {'─' * len(hdr_line)}")
        for row in data_rows:
            line = "  ".join(f"{str(v):<{w}s}" for v, w in zip(row, col_widths))
            out.info(f"  {line}")
        out.info(f"\n  {len(data_rows)} rows (preview)")
    else:
        for row in result[:limit]:
            out.info(f"  {row}")


@app.command("set-params")
def set_params(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    props: Annotated[str, typer.Option("--props", help="JSON properties definition")],
) -> None:
    """Configure query parameters for a SQL export.

    Parameters use %(Property Name)s syntax in the SQL query.

    Examples:
        kctl-odoo sql-export set-params 1 --props '[{"name":"company_id","type":"char","string":"Company ID"}]'
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    try:
        props_data = json.loads(props)
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from e

    try:
        c.execute_kw(_MODEL, "write", [[export_id], {"query_properties_definition": props_data}])
    except RPCError as e:
        out.error(f"Failed to set params: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Parameters set on SQL export #{export_id}")
    if actx.json_mode:
        out.raw_json({"id": export_id, "properties": props_data})


@app.command("grant")
def grant(
    ctx: typer.Context,
    export_id: Annotated[int, typer.Argument(help="SQL export ID")],
    users: Annotated[str | None, typer.Option("--users", "-u", help="Comma-separated user logins")] = None,
    groups: Annotated[str | None, typer.Option("--groups", "-g", help="Comma-separated group XML IDs")] = None,
    replace: Annotated[bool, typer.Option("--replace", help="Replace existing access (default: append)")] = False,
) -> None:
    """Manage who can execute a SQL export.

    By default appends to existing users/groups. Use --replace to overwrite.

    Examples:
        kctl-odoo sql-export grant 1 --users tri.gunawan,admin
        kctl-odoo sql-export grant 1 --groups base.group_system
        kctl-odoo sql-export grant 1 --users tri.gunawan --replace
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _check_module(c, out)

    vals: dict = {}

    if users:
        user_logins = [u.strip() for u in users.split(",")]
        try:
            user_records = c.search_read(
                "res.users",
                [("login", "in", user_logins)],
                ["id", "login"],
            )
        except RPCError as e:
            out.error(f"Failed to find users: {e.detail}")
            raise typer.Exit(1) from e

        found_logins = {u["login"] for u in user_records}
        missing = set(user_logins) - found_logins
        if missing:
            out.warning(f"Users not found: {', '.join(missing)}")

        user_ids = [u["id"] for u in user_records]
        if replace:
            vals["user_ids"] = [(6, 0, user_ids)]
        else:
            for uid in user_ids:
                vals.setdefault("user_ids", []).append((4, uid, False))

    if groups:
        group_refs = [g.strip() for g in groups.split(",")]
        group_ids = []
        for ref in group_refs:
            try:
                result = c.execute_kw("ir.model.data", "xmlid_to_res_id", [ref])
                if result:
                    group_ids.append(result)
                else:
                    out.warning(f"Group not found: {ref}")
            except RPCError:
                out.warning(f"Group not found: {ref}")

        if replace:
            vals["group_ids"] = [(6, 0, group_ids)]
        else:
            for gid in group_ids:
                vals.setdefault("group_ids", []).append((4, gid, False))

    if not vals:
        out.error("Specify --users and/or --groups.")
        raise typer.Exit(1)

    try:
        c.execute_kw(_MODEL, "write", [[export_id], vals])
    except RPCError as e:
        out.error(f"Failed to update access: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Access updated on SQL export #{export_id}")
