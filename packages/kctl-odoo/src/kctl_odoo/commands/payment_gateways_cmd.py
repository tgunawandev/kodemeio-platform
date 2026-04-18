"""Payment gateway status commands — iPaymu, Midtrans, Xendit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Payment gateways: iPaymu, Midtrans, Xendit status.")

_PROVIDER_MODEL = "payment.provider"
_TRANSACTION_MODEL = "payment.transaction"
_PROVIDER_HINT = "Payment provider model not available. Ensure Odoo payment module is installed."
_TRANSACTION_HINT = "Payment transaction model not available. Ensure Odoo payment module is installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# STATUS
# ===================================================================


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Show all payment providers with state.

    Examples:
        kctl-odoo payment-gateways status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _PROVIDER_MODEL):
        out.warn(_PROVIDER_HINT)
        return

    preferred = ["display_name", "state", "module_id", "company_id", "is_published"]
    fields = safe_fields(c, _PROVIDER_MODEL, preferred)

    try:
        providers = c.search_read(  # type: ignore[attr-defined]
            _PROVIDER_MODEL,
            domain=[],
            fields=fields,
            order="name asc",
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch payment providers: {e}")
        raise typer.Exit(1) from e

    if not providers:
        out.info("No payment providers configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for p in providers:
        rows.append(
            [
                str(p["id"]),
                p.get("display_name") or p.get("name", ""),
                str(p.get("state") or "-"),
                "Yes" if p.get("is_published") else "No",
                _m2o_name(p.get("module_id")),
                _m2o_name(p.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": p["id"],
                "name": p.get("display_name") or p.get("name"),
                "state": p.get("state"),
                "is_published": p.get("is_published"),
                "module": _m2o_name(p.get("module_id")),
                "company": _m2o_name(p.get("company_id")),
            }
        )

    out.table(
        f"Payment Providers ({len(providers)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("State", ""),
            ("Published", ""),
            ("Module", ""),
            ("Company", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PENDING
# ===================================================================


@app.command("pending")
def pending(
    ctx: typer.Context,
    provider: Annotated[str | None, typer.Option("--provider", help="Filter by provider name (partial match)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List pending payment transactions.

    Examples:
        kctl-odoo payment-gateways pending
        kctl-odoo payment-gateways pending --provider midtrans --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _TRANSACTION_MODEL):
        out.warn(_TRANSACTION_HINT)
        return

    domain: list = [("state", "=", "pending")]
    if provider:
        domain.append(("provider_id.name", "ilike", provider))

    preferred = ["display_name", "reference", "amount", "currency_id", "provider_id", "state", "create_date"]
    fields = safe_fields(c, _TRANSACTION_MODEL, preferred)

    try:
        txns = c.search_read(  # type: ignore[attr-defined]
            _TRANSACTION_MODEL,
            domain=domain,
            fields=fields,
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch pending transactions: {e}")
        raise typer.Exit(1) from e

    if not txns:
        out.info("No pending transactions found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for t in txns:
        rows.append(
            [
                str(t["id"]),
                str(t.get("reference") or t.get("display_name") or ""),
                f"{t.get('amount', 0.0) or 0.0:,.2f}",
                _m2o_name(t.get("currency_id")),
                _m2o_name(t.get("provider_id")),
                str(t.get("state") or ""),
                str(t.get("create_date") or ""),
            ]
        )
        json_data.append(
            {
                "id": t["id"],
                "reference": t.get("reference") or t.get("display_name"),
                "amount": t.get("amount"),
                "currency": _m2o_name(t.get("currency_id")),
                "provider": _m2o_name(t.get("provider_id")),
                "state": t.get("state"),
                "date": str(t.get("create_date") or ""),
            }
        )

    out.table(
        f"Pending Transactions ({len(txns)})",
        [
            ("ID", "dim"),
            ("Reference", "cyan"),
            ("Amount", ""),
            ("Currency", ""),
            ("Provider", ""),
            ("State", ""),
            ("Date", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# HISTORY
# ===================================================================


@app.command("history")
def history(
    ctx: typer.Context,
    provider: Annotated[str | None, typer.Option("--provider", help="Filter by provider name (partial match)")] = None,
    days: Annotated[int, typer.Option("--days", help="Days to look back")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List recent payment transactions.

    Examples:
        kctl-odoo payment-gateways history
        kctl-odoo payment-gateways history --provider ipaymu --days 7 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _TRANSACTION_MODEL):
        out.warn(_TRANSACTION_HINT)
        return

    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    domain: list = [("create_date", ">=", cutoff)]
    if provider:
        domain.append(("provider_id.name", "ilike", provider))

    preferred = ["display_name", "reference", "amount", "currency_id", "provider_id", "state", "create_date"]
    fields = safe_fields(c, _TRANSACTION_MODEL, preferred)

    try:
        txns = c.search_read(  # type: ignore[attr-defined]
            _TRANSACTION_MODEL,
            domain=domain,
            fields=fields,
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch transaction history: {e}")
        raise typer.Exit(1) from e

    if not txns:
        out.info(f"No transactions found in the last {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for t in txns:
        rows.append(
            [
                str(t["id"]),
                str(t.get("reference") or t.get("display_name") or ""),
                f"{t.get('amount', 0.0) or 0.0:,.2f}",
                _m2o_name(t.get("currency_id")),
                _m2o_name(t.get("provider_id")),
                str(t.get("state") or ""),
                str(t.get("create_date") or ""),
            ]
        )
        json_data.append(
            {
                "id": t["id"],
                "reference": t.get("reference") or t.get("display_name"),
                "amount": t.get("amount"),
                "currency": _m2o_name(t.get("currency_id")),
                "provider": _m2o_name(t.get("provider_id")),
                "state": t.get("state"),
                "date": str(t.get("create_date") or ""),
            }
        )

    out.table(
        f"Payment History — last {days} day(s) ({len(txns)})",
        [
            ("ID", "dim"),
            ("Reference", "cyan"),
            ("Amount", ""),
            ("Currency", ""),
            ("Provider", ""),
            ("State", ""),
            ("Date", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# RECONCILE
# ===================================================================


@app.command("reconcile")
def reconcile(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="List stale pending transactions without action")] = False,
) -> None:
    """Check for stale pending transactions (>24h) and suggest reconciliation.

    Lists payment transactions stuck in 'pending' state for over 24 hours.
    Actual reconciliation requires provider-specific API calls.

    Examples:
        kctl-odoo payment-gateways reconcile --dry-run
        kctl-odoo payment-gateways reconcile
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _TRANSACTION_MODEL):
        out.warn(_TRANSACTION_HINT)
        return

    cutoff = (datetime.now(UTC) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    preferred = ["display_name", "reference", "amount", "currency_id", "provider_id", "state", "create_date"]
    fields = safe_fields(c, _TRANSACTION_MODEL, preferred)

    try:
        stale = c.search_read(  # type: ignore[attr-defined]
            _TRANSACTION_MODEL,
            domain=[("state", "=", "pending"), ("create_date", "<=", cutoff)],
            fields=fields,
            order="create_date asc",
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch stale transactions: {e}")
        raise typer.Exit(1) from e

    if not stale:
        out.info("No stale pending transactions found (older than 24h).")
        if actx.json_mode:
            out.raw_json({"count": 0, "transactions": []})
        return

    rows = []
    json_data = []
    for t in stale:
        rows.append(
            [
                str(t["id"]),
                str(t.get("reference") or t.get("display_name") or ""),
                f"{t.get('amount', 0.0) or 0.0:,.2f}",
                _m2o_name(t.get("provider_id")),
                str(t.get("create_date") or ""),
            ]
        )
        json_data.append(
            {
                "id": t["id"],
                "reference": t.get("reference") or t.get("display_name"),
                "amount": t.get("amount"),
                "provider": _m2o_name(t.get("provider_id")),
                "date": str(t.get("create_date") or ""),
            }
        )

    out.table(
        f"Stale Pending Transactions (>24h) — {len(stale)} found",
        [
            ("ID", "dim"),
            ("Reference", "cyan"),
            ("Amount", ""),
            ("Provider", ""),
            ("Date", "red"),
        ],
        rows,
        data_for_json=json_data,
    )

    if dry_run:
        out.info("Dry-run: no changes made. Review transactions and reconcile via Odoo UI or provider dashboard.")
    else:
        out.warn(
            f"Found {len(stale)} stale pending transaction(s). "
            "Manual reconciliation required via provider dashboard "
            "(iPaymu: dashboard.ipaymu.com, Midtrans: dashboard.midtrans.com, Xendit: dashboard.xendit.co)."
        )

    if actx.json_mode:
        out.raw_json({"count": len(stale), "transactions": json_data})
