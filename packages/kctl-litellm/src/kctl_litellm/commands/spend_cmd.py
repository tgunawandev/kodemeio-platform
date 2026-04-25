"""Spend tracking commands for kctl-litellm.

View spend summaries and daily activity.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Track LiteLLM spend and usage.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command()
def summary(ctx: typer.Context) -> None:
    """Show total spend summary from /global/spend/logs."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        logs = client.spend_logs()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not logs:
        out.warn("No spend data found.")
        return

    # Aggregate spend by model
    model_spend: dict[str, float] = {}
    total_spend = 0.0
    total_requests = 0

    for log in logs:
        if not isinstance(log, dict):
            continue
        model = log.get("model", "unknown")
        spend = float(log.get("spend", 0))
        model_spend[model] = model_spend.get(model, 0) + spend
        total_spend += spend
        total_requests += 1

    table = Table(title="Spend Summary", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="cyan")
    table.add_column("Spend", justify="right")
    table.add_column("% of Total", justify="right")

    for model, spend in sorted(model_spend.items(), key=lambda x: x[1], reverse=True):
        pct = (spend / total_spend * 100) if total_spend > 0 else 0
        table.add_row(model, f"${spend:.4f}", f"{pct:.1f}%")

    rprint(table)
    out.kv("Total Spend", f"${total_spend:.4f}")
    out.kv("Total Requests", str(total_requests))


@app.command()
def daily(
    ctx: typer.Context,
    start_date: Annotated[
        str | None, typer.Option("--start-date", help="Start date (YYYY-MM-DD). Default: 7 days ago.")
    ] = None,
    end_date: Annotated[str | None, typer.Option("--end-date", help="End date (YYYY-MM-DD). Default: today.")] = None,
) -> None:
    """Show daily activity from /user/daily/activity."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        client = _get_client(actx)
        result = client.daily_activity(start_date, end_date)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    # Parse the daily activity response
    daily_data = result.get("daily_activity", result.get("data", []))
    if isinstance(daily_data, dict):
        daily_data = [daily_data]

    if not daily_data:
        out.warn(f"No activity data for {start_date} to {end_date}.")
        return

    table = Table(title=f"Daily Activity ({start_date} to {end_date})", show_header=True, header_style="bold cyan")
    table.add_column("Date", style="cyan")
    table.add_column("Requests", justify="right")
    table.add_column("Spend", justify="right")
    table.add_column("Tokens", justify="right")

    for day in daily_data:
        if not isinstance(day, dict):
            continue
        date = day.get("date", "unknown")
        requests = str(day.get("api_requests", day.get("total_requests", 0)))
        spend = f"${day.get('total_spend', day.get('spend', 0)):.4f}"
        tokens = str(day.get("total_tokens", day.get("tokens", 0)))
        table.add_row(date, requests, spend, tokens)

    rprint(table)
