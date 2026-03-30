"""Fixed asset management commands — depreciation, disposal, tracking."""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Fixed assets: depreciation, disposal, tracking.")

_ASSET_MODEL = "account.asset"
_ASSET_LINE_MODEL = "account.asset.line"
_ASSET_HINT = "Fixed asset module (account_asset_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_assets(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help="Filter by state: draft, open, close, removed")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List fixed assets.

    Examples:
        kctl-odoo assets list
        kctl-odoo assets list --state open --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _ASSET_MODEL):
        out.warn(_ASSET_HINT)
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    preferred = [
        "display_name",
        "code",
        "state",
        "purchase_value",
        "salvage_value",
        "depreciation_base",
        "profile_id",
        "date_start",
        "company_id",
    ]
    fields = safe_fields(c, _ASSET_MODEL, preferred)

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _ASSET_MODEL,
            domain=domain,
            fields=fields,
            limit=limit,
            order="date_start desc",
        )
    except RPCError as e:
        out.error(f"Failed to list assets: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No assets found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("display_name") or r.get("name", ""),
                r.get("code", "") or "",
                str(r.get("state", "")),
                f"{r.get('purchase_value', 0.0) or 0.0:,.2f}",
                _m2o_name(r.get("profile_id")),
                str(r.get("date_start", "") or ""),
                _m2o_name(r.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("display_name") or r.get("name"),
                "code": r.get("code"),
                "state": r.get("state"),
                "purchase_value": r.get("purchase_value"),
                "profile": _m2o_name(r.get("profile_id")),
                "date_start": str(r.get("date_start") or ""),
                "company": _m2o_name(r.get("company_id")),
            }
        )

    out.table(
        f"Fixed Assets ({len(records)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Code", ""),
            ("State", ""),
            ("Purchase Value", ""),
            ("Profile", ""),
            ("Date Start", ""),
            ("Company", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET
# ===================================================================


@app.command("get")
def get_asset(
    ctx: typer.Context,
    asset_id: Annotated[int, typer.Argument(help="Asset ID")],
) -> None:
    """Show asset detail.

    Examples:
        kctl-odoo assets get 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _ASSET_MODEL):
        out.warn(_ASSET_HINT)
        return

    preferred = [
        "display_name",
        "name",
        "code",
        "purchase_value",
        "salvage_value",
        "depreciation_base",
        "method",
        "method_number",
        "method_period",
        "date_start",
        "state",
        "profile_id",
        "company_id",
        "depreciation_line_ids",
    ]
    fields = safe_fields(c, _ASSET_MODEL, preferred)

    try:
        assets = c.read(  # type: ignore[attr-defined]
            _ASSET_MODEL,
            [asset_id],
            fields,
        )
    except RPCError as e:
        out.error(f"Failed to fetch asset {asset_id}: {e}")
        raise typer.Exit(1) from e

    if not assets:
        out.error(f"Asset not found: {asset_id}")
        raise typer.Exit(1)

    a = assets[0]
    dep_line_ids = a.get("depreciation_line_ids", [])

    # Count depreciation lines if not embedded
    if not dep_line_ids and model_available(c, _ASSET_LINE_MODEL):
        try:
            dep_count = c.search_count(  # type: ignore[attr-defined]
                _ASSET_LINE_MODEL, [("asset_id", "=", asset_id)]
            )
        except RPCError:
            dep_count = 0
    else:
        dep_count = len(dep_line_ids)

    sections = [
        (
            "Asset Detail",
            [
                ("ID", str(a["id"])),
                ("Name", a.get("display_name") or a.get("name", "")),
                ("Code", str(a.get("code") or "-")),
                ("State", str(a.get("state") or "-")),
                ("Purchase Value", f"{a.get('purchase_value', 0.0) or 0.0:,.2f}"),
                ("Salvage Value", f"{a.get('salvage_value', 0.0) or 0.0:,.2f}"),
                ("Depreciation Base", f"{a.get('depreciation_base', 0.0) or 0.0:,.2f}"),
                ("Method", str(a.get("method") or "-")),
                ("Method Number", str(a.get("method_number") or "-")),
                ("Method Period", str(a.get("method_period") or "-")),
                ("Date Start", str(a.get("date_start") or "-")),
                ("Profile", _m2o_name(a.get("profile_id"))),
                ("Company", _m2o_name(a.get("company_id"))),
                ("Depreciation Lines", str(dep_count)),
            ],
        )
    ]

    json_result = {
        "id": a["id"],
        "name": a.get("display_name") or a.get("name"),
        "code": a.get("code"),
        "state": a.get("state"),
        "purchase_value": a.get("purchase_value"),
        "salvage_value": a.get("salvage_value"),
        "depreciation_base": a.get("depreciation_base"),
        "method": a.get("method"),
        "method_number": a.get("method_number"),
        "method_period": a.get("method_period"),
        "date_start": str(a.get("date_start") or ""),
        "profile": _m2o_name(a.get("profile_id")),
        "company": _m2o_name(a.get("company_id")),
        "depreciation_lines_count": dep_count,
    }

    out.detail("Asset Detail", sections, data_for_json=json_result)


# ===================================================================
# DEPRECIATION-SCHEDULE
# ===================================================================


@app.command("depreciation-schedule")
def depreciation_schedule(
    ctx: typer.Context,
    asset_id: Annotated[int, typer.Argument(help="Asset ID")],
) -> None:
    """Show depreciation schedule for an asset.

    Examples:
        kctl-odoo assets depreciation-schedule 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _ASSET_LINE_MODEL):
        out.warn(_ASSET_HINT)
        return

    preferred = ["display_name", "line_date", "amount", "remaining_value", "type", "move_id"]
    fields = safe_fields(c, _ASSET_LINE_MODEL, preferred)

    try:
        lines = c.search_read(  # type: ignore[attr-defined]
            _ASSET_LINE_MODEL,
            domain=[("asset_id", "=", asset_id)],
            fields=fields,
            order="line_date asc",
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch depreciation lines for asset {asset_id}: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info(f"No depreciation lines found for asset {asset_id}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for ln in lines:
        move_posted = "Yes" if ln.get("move_id") else "No"
        rows.append(
            [
                str(ln.get("line_date") or ""),
                f"{ln.get('amount', 0.0) or 0.0:,.2f}",
                f"{ln.get('remaining_value', 0.0) or 0.0:,.2f}",
                str(ln.get("type") or ""),
                move_posted,
            ]
        )
        json_data.append(
            {
                "line_date": str(ln.get("line_date") or ""),
                "amount": ln.get("amount"),
                "remaining_value": ln.get("remaining_value"),
                "type": ln.get("type"),
                "move_posted": bool(ln.get("move_id")),
            }
        )

    out.table(
        f"Depreciation Schedule — Asset {asset_id} ({len(lines)} lines)",
        [
            ("Date", ""),
            ("Amount", ""),
            ("Remaining Value", ""),
            ("Type", ""),
            ("Move Posted", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# POST-DEPRECIATION
# ===================================================================


@app.command("post-depreciation")
def post_depreciation(
    ctx: typer.Context,
    dep_date: Annotated[
        str | None, typer.Option("--date", help="Post lines up to this date (YYYY-MM-DD), default: today")
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show lines to post without posting")] = False,
) -> None:
    """Trigger depreciation posting for pending lines.

    Examples:
        kctl-odoo assets post-depreciation --dry-run
        kctl-odoo assets post-depreciation --date 2025-12-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _ASSET_LINE_MODEL):
        out.warn(_ASSET_HINT)
        return

    target_date = dep_date or date.today().strftime("%Y-%m-%d")

    preferred = ["display_name", "line_date", "amount", "asset_id", "type"]
    fields = safe_fields(c, _ASSET_LINE_MODEL, preferred)

    try:
        pending = c.search_read(  # type: ignore[attr-defined]
            _ASSET_LINE_MODEL,
            domain=[
                ("type", "=", "depreciate"),
                ("move_id", "=", False),
                ("line_date", "<=", target_date),
            ],
            fields=fields,
            order="line_date asc",
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch pending depreciation lines: {e}")
        raise typer.Exit(1) from e

    if not pending:
        out.info(f"No pending depreciation lines up to {target_date}.")
        if actx.json_mode:
            out.raw_json({"count": 0, "date": target_date, "posted": 0})
        return

    out.info(f"Found {len(pending)} pending depreciation line(s) up to {target_date}.")

    rows = []
    json_data = []
    for ln in pending:
        rows.append(
            [
                str(ln.get("line_date") or ""),
                _m2o_name(ln.get("asset_id")),
                f"{ln.get('amount', 0.0) or 0.0:,.2f}",
            ]
        )
        json_data.append(
            {
                "id": ln["id"],
                "line_date": str(ln.get("line_date") or ""),
                "asset": _m2o_name(ln.get("asset_id")),
                "amount": ln.get("amount"),
            }
        )

    out.table(
        f"Pending Depreciation Lines ({len(pending)})",
        [("Date", ""), ("Asset", "cyan"), ("Amount", "")],
        rows,
        data_for_json=json_data,
    )

    if dry_run:
        out.info("Dry-run mode — no lines were posted.")
        return

    # Attempt to create moves
    posted_count = 0
    errors = 0
    line_ids = [ln["id"] for ln in pending]

    try:
        c.execute_kw(  # type: ignore[attr-defined]
            _ASSET_LINE_MODEL, "create_move", [line_ids]
        )
        posted_count = len(line_ids)
        out.success(f"Posted {posted_count} depreciation line(s).")
    except RPCError as e:
        out.warn(f"Batch create_move failed, trying individually: {e}")
        for ln in pending:
            try:
                c.execute_kw(  # type: ignore[attr-defined]
                    _ASSET_LINE_MODEL, "create_move", [[ln["id"]]]
                )
                posted_count += 1
            except RPCError as ie:
                out.warn(f"  Line {ln['id']} failed: {ie}")
                errors += 1

    if actx.json_mode:
        out.raw_json(
            {
                "count": len(pending),
                "date": target_date,
                "posted": posted_count,
                "errors": errors,
            }
        )
    else:
        if errors:
            out.warn(f"Posted {posted_count}/{len(pending)} lines ({errors} errors).")
        else:
            out.success(f"Successfully posted {posted_count} depreciation line(s).")


# ===================================================================
# SUMMARY
# ===================================================================


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """Asset statistics — counts and values by state.

    Examples:
        kctl-odoo assets summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _ASSET_MODEL):
        out.warn(_ASSET_HINT)
        return

    states = ["draft", "open", "close", "removed"]
    state_stats: list[dict] = []

    total_purchase = 0.0
    total_base = 0.0

    for st in states:
        try:
            count = c.search_count(  # type: ignore[attr-defined]
                _ASSET_MODEL, [("state", "=", st)]
            )
            if count > 0:
                records = c.search_read(  # type: ignore[attr-defined]
                    _ASSET_MODEL,
                    domain=[("state", "=", st)],
                    fields=["purchase_value", "depreciation_base"],
                    limit=0,
                )
                purchase_sum = sum(r.get("purchase_value", 0.0) or 0.0 for r in records)
                base_sum = sum(r.get("depreciation_base", 0.0) or 0.0 for r in records)
            else:
                purchase_sum = base_sum = 0.0
        except RPCError:
            count = 0
            purchase_sum = base_sum = 0.0

        total_purchase += purchase_sum
        total_base += base_sum
        state_stats.append(
            {
                "state": st,
                "count": count,
                "purchase_value": purchase_sum,
                "depreciation_base": base_sum,
            }
        )

    # Count pending depreciation lines
    pending_dep = 0
    if model_available(c, _ASSET_LINE_MODEL):
        try:
            today_str = date.today().strftime("%Y-%m-%d")
            pending_dep = c.search_count(  # type: ignore[attr-defined]
                _ASSET_LINE_MODEL,
                [("type", "=", "depreciate"), ("move_id", "=", False), ("line_date", "<=", today_str)],
            )
        except RPCError:
            pending_dep = 0

    sections = [
        (
            "Asset Statistics",
            [
                (
                    s["state"].capitalize(),
                    f"{s['count']} assets | Purchase: {s['purchase_value']:,.2f} | Base: {s['depreciation_base']:,.2f}",
                )
                for s in state_stats
            ]
            + [
                ("Total Purchase Value", f"{total_purchase:,.2f}"),
                ("Total Depreciation Base", f"{total_base:,.2f}"),
                ("Pending Depreciation Lines", str(pending_dep)),
            ],
        )
    ]

    json_result = {
        "by_state": state_stats,
        "total_purchase_value": total_purchase,
        "total_depreciation_base": total_base,
        "pending_depreciation_lines": pending_dep,
    }

    out.detail("Asset Summary", sections, data_for_json=json_result)
