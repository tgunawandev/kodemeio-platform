"""Report template management: import/export/clone/library install.

Wraps the ``report.template`` RPC helpers shipped with ``report_management``
(kodemeio-odoo commits ``6b2e7741`` + ``53f1ffdc``):

    * ``env["report.template"].import_json(data, update_existing=False)``
    * ``tpl.export_json()``
    * ``tpl.duplicate_with_lines(new_name, new_code=None)``
    * ``env["report.template"].library_list()``
    * ``env["report.template"].library_install(name_or_file, update_existing=False)``

Mounted under the existing ``report`` command group as ``report template``
so it does not collide with the existing ``report list`` (ir.actions.report)
and ``report export`` (instance PDF/XLSX download) subcommands — these new
commands operate on ``report.template`` records, a different concern.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report template management: import/export/clone/library install.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_report_management(c, out) -> bool:
    """Return True if report_management (report.template) is installed.

    Emits a user-facing warn via ``out`` when missing, so callers just
    ``return`` or ``raise typer.Exit(1)`` on False.
    """
    if not model_available(c, "report.template"):
        out.warn("report.template model not available. Install with: kctl-odoo modules install report_management")
        return False
    return True


def _record_id(val: object) -> int | None:
    """Normalize RPC return values that may be an int, a list of ints, or None.

    Odoo's JSON-RPC serializes single records as their ID, but recordsets
    may come back as lists in some layers. This shim gives a single int.
    """
    if isinstance(val, list):
        if not val:
            return None
        first = val[0]
        return int(first) if isinstance(first, int) else None
    if isinstance(val, int):
        return val
    return None


def _resolve_template_id(c, code: str) -> int | None:
    """Return the id of the template with this ``code`` or ``None``."""
    ids = c.search("report.template", [("code", "=", code)], limit=1)
    return ids[0] if ids else None


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command("list")
def list_templates(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (e.g. financial, sales)"),
    ] = None,
    report_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by report_type code"),
    ] = None,
) -> None:
    """List ``report.template`` records on the connected tenant.

    Examples:
        kctl-odoo report template list
        kctl-odoo report template list --category financial
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    domain: list = []
    if category:
        domain.append(("category", "=", category))
    if report_type:
        domain.append(("report_type", "=", report_type))

    rows = c.search_read(
        "report.template",
        domain=domain,
        fields=["id", "code", "name", "category", "report_type", "company_id", "sequence"],
        order="category, sequence, name",
    )
    if not rows:
        out.info("No templates found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = []
    for r in rows:
        company = r.get("company_id")
        company_display = company[1] if isinstance(company, list) else "-"
        table_rows.append(
            [
                str(r.get("id", "")),
                r.get("code") or "-",
                (r.get("name") or "")[:40],
                r.get("category") or "-",
                r.get("report_type") or "-",
                company_display,
            ]
        )

    out.table(
        f"Report Templates ({len(rows)})",
        [
            ("ID", "dim"),
            ("Code", "cyan"),
            ("Name", ""),
            ("Category", ""),
            ("Type", ""),
            ("Company", "dim"),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
@app.command("export")
def export_template(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Template code to export")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if omitted)"),
    ] = None,
) -> None:
    """Dump a template to JSON.

    Without ``-o``, prints JSON to stdout for piping (e.g. ``| jq .``).

    Examples:
        kctl-odoo report template export pnl_management -o pnl.json
        kctl-odoo report template export bs_ifrs | jq .
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    tpl_id = _resolve_template_id(c, code)
    if tpl_id is None:
        out.error(f"Template not found: {code}")
        raise typer.Exit(1)

    try:
        data = c.execute_kw("report.template", "export_json", [[tpl_id]])
    except RPCError as exc:
        out.error(f"Export failed: {exc}")
        raise typer.Exit(1) from exc

    payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)

    if output:
        output.write_text(payload, encoding="utf-8")
        out.success(f"Wrote {output}")
        if actx.json_mode:
            out.raw_json({"code": code, "file": str(output), "size": len(payload)})
    else:
        # Print the JSON unadorned so the output is pipe-safe.
        print(payload)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------
@app.command("import")
def import_template(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="JSON file to import")],
    update: Annotated[
        bool,
        typer.Option("--update", help="Replace existing template with same code"),
    ] = False,
) -> None:
    """Load a JSON file as a new template.

    Use ``--update`` to replace an existing template with the same code
    in the current company (lines + subkpis are REPLACED, not merged).

    Examples:
        kctl-odoo report template import pnl.json
        kctl-odoo report template import pnl.json --update
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    if not file.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except ValueError as exc:
        out.error(f"Invalid JSON: {exc}")
        raise typer.Exit(1) from exc
    except OSError as exc:
        out.error(f"Cannot read file: {exc}")
        raise typer.Exit(1) from exc

    if not isinstance(data, dict) or "code" not in data:
        out.error("JSON payload must be an object with at least a 'code' field.")
        raise typer.Exit(1)

    try:
        # import_json is @api.model — pass [] for recordset args, kwargs for params.
        result = c.execute_kw(
            "report.template",
            "import_json",
            [],
            {"data": data, "update_existing": update},
        )
    except RPCError as exc:
        out.error(f"Import failed: {exc}")
        raise typer.Exit(1) from exc

    tpl_id = _record_id(result)
    out.success(f"Imported template {data.get('code')!r}" + (f" (id={tpl_id})" if tpl_id is not None else ""))
    if actx.json_mode:
        out.raw_json({"code": data.get("code"), "id": tpl_id, "updated": update})


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------
@app.command("clone")
def clone_template(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Source template code")],
    name: Annotated[str, typer.Option("--name", "-n", help="Display name for the new template")],
    new_code: Annotated[
        str | None,
        typer.Option("--new-code", help="New code (auto-generated if omitted)"),
    ] = None,
) -> None:
    """Duplicate an existing template with all its lines and subkpis.

    Examples:
        kctl-odoo report template clone pnl_management --name "P&L Sub X"
        kctl-odoo report template clone bs_ifrs --name "BS Consolidated" --new-code bs_consolidated
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    tpl_id = _resolve_template_id(c, code)
    if tpl_id is None:
        out.error(f"Source template not found: {code}")
        raise typer.Exit(1)

    kwargs: dict = {"new_name": name}
    if new_code:
        kwargs["new_code"] = new_code

    try:
        result = c.execute_kw("report.template", "duplicate_with_lines", [[tpl_id]], kwargs)
    except RPCError as exc:
        out.error(f"Clone failed: {exc}")
        raise typer.Exit(1) from exc

    new_id = _record_id(result)
    out.success(f"Cloned {code!r} -> {name!r}" + (f" (id={new_id})" if new_id is not None else ""))
    if actx.json_mode:
        out.raw_json({"source_code": code, "new_name": name, "new_code": new_code, "id": new_id})


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------
@app.command("library")
def library_list(ctx: typer.Context) -> None:
    """List bundled templates discoverable via ``library_list()``.

    Shows templates shipped under ``<module>/data/templates/*.json`` by any
    installed addon. Any of these can be installed via
    ``kctl-odoo report template install <code-or-filename>``.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    try:
        # library_list is @api.model — no recordset args.
        entries = c.execute_kw("report.template", "library_list", [])
    except RPCError as exc:
        out.error(f"library_list failed: {exc}")
        raise typer.Exit(1) from exc

    if not entries:
        out.info("No bundled templates found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for e in entries:
        rows.append(
            [
                e.get("code") or "-",
                (e.get("name") or "")[:40],
                e.get("category") or "-",
                e.get("report_type") or "-",
                e.get("module") or "-",
                e.get("file") or "-",
            ]
        )
    out.table(
        f"Bundled Templates ({len(entries)})",
        [
            ("Code", "cyan"),
            ("Name", ""),
            ("Category", ""),
            ("Type", ""),
            ("Module", "dim"),
            ("File", "dim"),
        ],
        rows,
        data_for_json=entries,
    )


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
@app.command("install")
def library_install(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Template code or JSON filename")],
    update: Annotated[
        bool,
        typer.Option("--update", help="Replace existing if code collides"),
    ] = False,
) -> None:
    """Install a bundled template by code or filename.

    Examples:
        kctl-odoo report template install pnl_management
        kctl-odoo report template install pnl_management.json --update
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    try:
        result = c.execute_kw(
            "report.template",
            "library_install",
            [],
            {"name_or_file": name, "update_existing": update},
        )
    except RPCError as exc:
        out.error(f"Install failed: {exc}")
        raise typer.Exit(1) from exc

    tpl_id = _record_id(result)
    out.success(f"Installed bundled template {name!r}" + (f" (id={tpl_id})" if tpl_id is not None else ""))
    if actx.json_mode:
        out.raw_json({"name": name, "id": tpl_id, "updated": update})


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_template(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Template code to display")],
) -> None:
    """Display template details — metadata, lines, and subkpis.

    Uses ``export_json`` under the hood so the output matches what
    ``report template export`` would serialize.

    Examples:
        kctl-odoo report template show pnl_management
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    tpl_id = _resolve_template_id(c, code)
    if tpl_id is None:
        out.error(f"Template not found: {code}")
        raise typer.Exit(1)

    try:
        data = c.execute_kw("report.template", "export_json", [[tpl_id]])
    except RPCError as exc:
        out.error(f"Failed to read template: {exc}")
        raise typer.Exit(1) from exc

    if actx.json_mode:
        out.raw_json(data)
        return

    out.info(f"Name:     {data.get('name')}")
    out.info(f"Code:     {data.get('code')}")
    out.info(f"Category: {data.get('category')}    Type: {data.get('report_type')}")
    out.info(f"Sequence: {data.get('sequence')}    Schema: v{data.get('schema_version')}")
    if data.get("description"):
        out.info(f"Notes:    {data['description']}")
    out.info(f"Lines:    {len(data.get('lines', []))}")
    out.info(f"SubKPIs:  {len(data.get('subkpis', []))}")

    lines = data.get("lines") or []
    if lines:
        rows = []
        for ln in lines:
            rows.append(
                [
                    str(ln.get("sequence", "")),
                    ln.get("code") or "-",
                    (ln.get("name") or "")[:40],
                    ln.get("line_type") or "-",
                    (ln.get("expression") or "")[:30] or "-",
                    (ln.get("formula") or "")[:30] or "-",
                ]
            )
        out.table(
            "Lines",
            [
                ("Seq", "dim"),
                ("Code", "cyan"),
                ("Name", ""),
                ("Type", ""),
                ("AEP", ""),
                ("Formula", ""),
            ],
            rows,
            data_for_json=lines,
        )

    subkpis = data.get("subkpis") or []
    if subkpis:
        rows = []
        for k in subkpis:
            rows.append(
                [
                    str(k.get("sequence", "")),
                    k.get("code") or "-",
                    (k.get("name") or "")[:30],
                    (k.get("formula") or "")[:40] or "-",
                    k.get("display_format") or "-",
                ]
            )
        out.table(
            "SubKPIs",
            [
                ("Seq", "dim"),
                ("Code", "cyan"),
                ("Name", ""),
                ("Formula", ""),
                ("Format", ""),
            ],
            rows,
            data_for_json=subkpis,
        )


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_template(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Template code to delete")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip interactive confirmation"),
    ] = False,
) -> None:
    """Delete a template by code.

    Removes the template record along with its lines and subkpis (via ORM
    cascade). Linked ``report.instance`` records block deletion with an
    RPCError — detach or delete those first.

    Examples:
        kctl-odoo report template delete pnl_management_copy_1 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _require_report_management(c, out):
        raise typer.Exit(1)

    tpl_id = _resolve_template_id(c, code)
    if tpl_id is None:
        out.error(f"Template not found: {code}")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete template {code!r} (id={tpl_id})?")
        if not confirm:
            out.info("Aborted.")
            return

    try:
        c.unlink("report.template", [tpl_id])
    except RPCError as exc:
        out.error(f"Delete failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Deleted template {code!r}")
    if actx.json_mode:
        out.raw_json({"code": code, "id": tpl_id, "deleted": True})
