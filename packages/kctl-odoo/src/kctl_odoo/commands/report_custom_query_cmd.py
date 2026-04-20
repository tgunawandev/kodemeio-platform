"""Report custom-query (non-ledger data source) CRUD.

Wraps the ``report.custom.query`` model — a sandboxed domain + groupby +
aggregate over any Odoo model. Lets a report template pull data from
``sale.order.line``, ``hr.payslip``, ``stock.move`` etc. without writing
a new handler. Operators can create, tweak, preview, and drop these queries
from the CLI.

Mounted under ``kctl-odoo report custom-query``.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report custom-query (non-ledger data sources) CRUD.")


_WRITABLE = ("name", "model_id", "domain", "group_by", "measure", "aggregator", "company_id")


def _require_module(c, out) -> bool:
    if not model_available(c, "report.custom.query"):
        out.warn("report.custom.query not available. Install: kctl-odoo modules install report_management")
        return False
    return True


def _resolve_id(c, name: str) -> int | None:
    ids = c.search("report.custom.query", [("name", "=", name)], limit=1)
    return ids[0] if ids else None


def _resolve_model_id(c, model_name: str) -> int | None:
    ids = c.search("ir.model", [("model", "=", model_name)], limit=1)
    return ids[0] if ids else None


def _parse_kv(pairs: list[str] | None) -> dict:
    out: dict = {}
    for raw in pairs or []:
        if "=" not in raw:
            raise typer.BadParameter(f"Expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        if key not in _WRITABLE:
            raise typer.BadParameter(f"Unknown field {key!r}. Writable: {', '.join(_WRITABLE)}")
        val = val.strip()
        try:
            out[key] = json.loads(val)
        except ValueError:
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command("list")
def list_queries(
    ctx: typer.Context,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Filter by target model name"),
    ] = None,
) -> None:
    """List custom queries."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    domain: list = []
    if model:
        domain.append(("model_name", "=", model))
    rows = c.search_read(
        "report.custom.query",
        domain=domain,
        fields=[
            "id",
            "name",
            "model_name",
            "domain",
            "group_by",
            "measure",
            "aggregator",
            "company_id",
        ],
        order="name",
    )
    if not rows:
        out.info("No custom queries found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            (r.get("name") or "")[:24],
            r.get("model_name") or "-",
            (r.get("group_by") or "")[:18],
            (r.get("measure") or "")[:18],
            r.get("aggregator") or "-",
            (r.get("domain") or "[]")[:40],
            (r["company_id"][1] if isinstance(r.get("company_id"), list) else "-"),
        ]
        for r in rows
    ]
    out.table(
        f"Custom Queries ({len(rows)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("GroupBy", ""),
            ("Measure", ""),
            ("Agg", ""),
            ("Domain", "dim"),
            ("Company", "dim"),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_query(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Custom query name")],
) -> None:
    """Show one custom query in detail."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    qid = _resolve_id(c, name)
    if qid is None:
        out.error(f"Custom query not found: {name}")
        raise typer.Exit(1)
    (rec,) = c.read(
        "report.custom.query",
        [qid],
        [
            "id",
            "name",
            "model_id",
            "model_name",
            "domain",
            "group_by",
            "measure",
            "aggregator",
            "company_id",
        ],
    )
    if actx.json_mode:
        out.raw_json(rec)
        return
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command("create")
def create_query(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique query name")],
    model: Annotated[str, typer.Argument(help="Target model technical name, e.g. 'sale.order.line'")],
    group_by: Annotated[str, typer.Argument(help="Dotted field path, e.g. 'order_id.user_id'")],
    measure: Annotated[str, typer.Argument(help="Numeric field to aggregate, e.g. 'price_subtotal'")],
    aggregator: Annotated[
        str,
        typer.Option("--agg", help="sum / avg / count / min / max"),
    ] = "sum",
    domain: Annotated[
        str,
        typer.Option(
            "--domain",
            "-d",
            help="Python-domain string. `today`, `uid`, `date_from`, `date_to` in scope.",
        ),
    ] = "[]",
) -> None:
    """Create a new custom query.

    Example:

    \b
        kctl-odoo report custom-query create revenue_by_salesperson sale.order.line \\
            order_id.user_id price_subtotal \\
            --agg sum \\
            --domain "[('state', 'in', ['sale','done']), ('order_id.date_order', '>=', date_from), ('order_id.date_order', '<=', date_to)]"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    if _resolve_id(c, name) is not None:
        out.error(f"Custom query already exists: {name}. Use `update` to modify.")
        raise typer.Exit(1)

    model_id = _resolve_model_id(c, model)
    if model_id is None:
        out.error(f"ir.model not found: {model!r}")
        raise typer.Exit(1)

    vals = {
        "name": name,
        "model_id": model_id,
        "domain": domain,
        "group_by": group_by,
        "measure": measure,
        "aggregator": aggregator,
    }
    try:
        res = c.execute_kw("report.custom.query", "create", [vals])
    except RPCError as exc:
        out.error(f"Create failed: {exc}")
        raise typer.Exit(1) from exc
    new_id = res[0] if isinstance(res, list) else res
    out.success(f"Created report.custom.query name={name!r} id={new_id}")
    if actx.json_mode:
        out.raw_json({"name": name, "id": new_id})


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command("update")
def update_query(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Custom query name")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable)"),
    ],
) -> None:
    """Update fields on a custom query."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    qid = _resolve_id(c, name)
    if qid is None:
        out.error(f"Custom query not found: {name}")
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to update.")
        raise typer.Exit(1)

    try:
        c.execute_kw("report.custom.query", "write", [[qid], vals])
    except RPCError as exc:
        out.error(f"Update failed: {exc}")
        raise typer.Exit(1) from exc
    out.success(f"Updated report.custom.query id={qid}: {', '.join(vals.keys())}")
    if actx.json_mode:
        out.raw_json({"id": qid, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_query(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Custom query name")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a custom query by name."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    qid = _resolve_id(c, name)
    if qid is None:
        out.error(f"Custom query not found: {name}")
        raise typer.Exit(1)

    if not yes and not typer.confirm(f"Delete custom query {name!r}?"):
        raise typer.Exit(0)

    c.execute_kw("report.custom.query", "unlink", [[qid]])
    out.success(f"Deleted report.custom.query name={name!r}")
    if actx.json_mode:
        out.raw_json({"name": name, "id": qid, "deleted": True})


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------
@app.command("preview")
def preview_query(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Custom query name")],
    date_from: Annotated[
        str | None,
        typer.Option("--date-from", help="ISO date bound (for date-aware domains)"),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--date-to", help="ISO date bound"),
    ] = None,
) -> None:
    """Execute the query right now and print rows — sanity-check before attaching it to a template.

    Calls the server's ``execute()`` method, so output matches exactly what
    the report engine sees at render time.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    qid = _resolve_id(c, name)
    if qid is None:
        out.error(f"Custom query not found: {name}")
        raise typer.Exit(1)

    kwargs = {}
    if date_from:
        kwargs["date_from"] = date_from
    if date_to:
        kwargs["date_to"] = date_to

    try:
        (rows,) = c.execute_kw("report.custom.query", "execute", [[qid]], kwargs)
    except RPCError as exc:
        out.error(f"Preview failed: {exc}")
        raise typer.Exit(1) from exc

    if not rows:
        out.info("Query returned no rows.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [[str(r.get("group_key")), str(r.get("group_label") or "-"), f"{r.get('value'):,.2f}"] for r in rows]
    out.table(
        f"Custom Query: {name} ({len(rows)} groups)",
        [("Key", "dim"), ("Label", "cyan"), ("Value", "")],
        table_rows,
        data_for_json=rows,
    )
