"""Currency management and exchange rate automation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Currency management and exchange rate automation.")


@app.command("rates")
def rates(
    ctx: typer.Context,
    code: Annotated[str | None, typer.Option("--code", "-c", help="Filter by currency code (e.g. IDR, EUR)")] = None,
    days: Annotated[int, typer.Option("--days", "-d", help="Show rates from last N days")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of rates to show")] = 50,
) -> None:
    """List recent exchange rates.

    Queries res.currency.rate for recent exchange rate history.

    Examples:
        kctl-odoo currency rates
        kctl-odoo currency rates --code IDR
        kctl-odoo currency rates --days 7 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

    domain: list = [("name", ">=", cutoff)]

    if code:
        # Find currency id by name
        currencies = c.search_read(
            "res.currency",
            domain=[("name", "=ilike", code)],
            fields=["id", "name"],
            limit=5,
        )
        if not currencies:
            out.error(f"Currency '{code}' not found.")
            raise typer.Exit(1)
        currency_ids = [cur["id"] for cur in currencies]
        domain.append(("currency_id", "in", currency_ids))

    rate_records = c.search_read(
        "res.currency.rate",
        domain=domain,
        fields=["currency_id", "name", "rate", "company_id"],
        limit=limit,
        order="name desc",
    )

    if not rate_records:
        out.info(f"No exchange rates found{' for ' + code if code else ''} in the last {days} days.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for r in rate_records:
        currency = r.get("currency_id")
        currency_name = currency[1] if isinstance(currency, list) else str(currency or "")
        company = r.get("company_id")
        company_name = company[1] if isinstance(company, list) else str(company or "")
        rate_val = r.get("rate", 0)
        rows.append([currency_name, r.get("name", ""), f"{rate_val:.6f}", company_name])

    out.table(
        f"Exchange Rates (last {days} days)",
        [("Currency", "cyan"), ("Date", ""), ("Rate", ""), ("Company", "dim")],
        rows,
        data_for_json=rate_records,
    )

    if actx.json_mode:
        out.raw_json(rate_records)


@app.command("update")
def update(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Force trigger even if recently run")] = False,
) -> None:
    """Trigger currency rate update via Odoo cron.

    Looks for an ir.cron with 'Currency' in the name and triggers it directly.

    Examples:
        kctl-odoo currency update
        kctl-odoo currency update --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find the currency rate cron
    crons = c.search_read(
        "ir.cron",
        domain=[("name", "ilike", "currency")],
        fields=["id", "name", "active", "lastcall"],
        limit=5,
    )

    if not crons:
        out.error("No currency-related scheduled action found. Ensure the currency rate provider module is installed.")
        raise typer.Exit(1)

    # Use the first match
    cron = crons[0]
    out.info(f"Found cron: {cron['name']} (id={cron['id']})")

    if not cron.get("active") and not force:
        out.warn("Cron is inactive. Use --force to trigger anyway.")
        raise typer.Exit(1)

    try:
        c.execute_kw("ir.cron", "method_direct_trigger", [[cron["id"]]])
        out.success(f"Currency rate update triggered: '{cron['name']}'.")
    except Exception as e:
        out.error(f"Failed to trigger currency rate update: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"cron_id": cron["id"], "cron_name": cron["name"], "triggered": True})


@app.command("add")
def add(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Currency code to activate (e.g. IDR, EUR, USD)")],
) -> None:
    """Activate a currency by code.

    Searches res.currency by name (ISO code) and sets active=True.

    Examples:
        kctl-odoo currency add IDR
        kctl-odoo currency add EUR
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    currencies = c.search_read(
        "res.currency",
        domain=[("name", "=ilike", code)],
        fields=["id", "name", "active"],
        limit=5,
    )

    if not currencies:
        out.error(f"Currency '{code}' not found. Check the ISO currency code.")
        raise typer.Exit(1)

    currency = currencies[0]
    if currency.get("active"):
        out.info(f"Currency '{currency['name']}' is already active.")
        if actx.json_mode:
            out.raw_json({"id": currency["id"], "name": currency["name"], "active": True, "changed": False})
        return

    try:
        c.execute_kw("res.currency", "write", [[currency["id"]], {"active": True}])
        out.success(f"Currency '{currency['name']}' activated successfully.")
    except Exception as e:
        out.error(f"Failed to activate currency '{code}': {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"id": currency["id"], "name": currency["name"], "active": True, "changed": True})


@app.command("check-stale")
def check_stale(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Flag currencies with no rate in last N days")] = 7,
) -> None:
    """Flag currencies with outdated exchange rates.

    For each active currency, checks if there is at least one rate entry
    within the last N days. Reports currencies that may need updating.

    Examples:
        kctl-odoo currency check-stale
        kctl-odoo currency check-stale --days 3
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get all active currencies
    active_currencies = c.search_read(
        "res.currency",
        domain=[("active", "=", True)],
        fields=["id", "name"],
    )

    if not active_currencies:
        out.info("No active currencies found.")
        if actx.json_mode:
            out.raw_json([])
        return

    stale = []
    fresh = []

    for cur in active_currencies:
        recent_rates = c.search_count(
            "res.currency.rate",
            [("currency_id", "=", cur["id"]), ("name", ">=", cutoff)],
        )
        if recent_rates == 0:
            stale.append(cur["name"])
        else:
            fresh.append(cur["name"])

    rows = []
    for name in stale:
        rows.append([name, "[red]STALE[/red]", f"No rate in last {days} days"])
    for name in fresh:
        rows.append([name, "[green]OK[/green]", f"Has rate within {days} days"])

    out.table(
        f"Currency Rate Freshness (threshold: {days} days)",
        [("Currency", "cyan"), ("Status", ""), ("Note", "dim")],
        rows,
    )

    if stale:
        out.warn(f"{len(stale)} stale currency(ies): {', '.join(stale)}. Run 'kctl-odoo currency update' to refresh.")
    else:
        out.success(f"All {len(fresh)} active currencies have recent rates.")

    if actx.json_mode:
        out.raw_json({"stale": stale, "fresh": fresh, "days": days})
