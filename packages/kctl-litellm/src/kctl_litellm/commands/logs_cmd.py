"""Spend log commands for kctl-litellm.

View detailed request-level spend logs.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="View LiteLLM request spend logs.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum number of logs to show.")] = 25,
    start_date: Annotated[
        str | None, typer.Option("--start-date", help="Filter logs from this date (YYYY-MM-DD).")
    ] = None,
    end_date: Annotated[
        str | None, typer.Option("--end-date", help="Filter logs until this date (YYYY-MM-DD).")
    ] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Filter by API key hash.")] = None,
) -> None:
    """List spend logs from /global/spend/logs.

    Example: kctl-litellm logs list --limit 50 --start-date 2024-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output

    params: dict = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if api_key:
        params["api_key"] = api_key

    try:
        client = _get_client(actx)
        logs = client.spend_logs(**params)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not logs:
        out.warn("No spend logs found.")
        return

    # Truncate to limit
    display_logs = logs[:limit]

    table = Table(
        title=f"Spend Logs (showing {len(display_logs)} of {len(logs)})", show_header=True, header_style="bold cyan"
    )
    table.add_column("Request ID", style="cyan", max_width=20)
    table.add_column("Model")
    table.add_column("Spend", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Status")
    table.add_column("Timestamp", max_width=20)

    for log in display_logs:
        if not isinstance(log, dict):
            continue
        request_id = (
            (log.get("request_id", "")[:18] + "..")
            if len(log.get("request_id", "")) > 20
            else log.get("request_id", "")
        )
        model = log.get("model", "unknown")
        spend = f"${log.get('spend', 0):.6f}"
        total_tokens = str(log.get("total_tokens", log.get("completion_tokens", 0) + log.get("prompt_tokens", 0)))
        status = log.get("status", "")
        if status == "success":
            status = "[green]success[/green]"
        elif status:
            status = f"[red]{status}[/red]"
        timestamp = log.get("startTime", log.get("start_time", ""))
        if isinstance(timestamp, str) and len(timestamp) > 20:
            timestamp = timestamp[:19]
        table.add_row(request_id, model, spend, total_tokens, status, str(timestamp))

    rprint(table)

    # Show total spend for displayed logs
    total = sum(float(l.get("spend", 0)) for l in display_logs if isinstance(l, dict))
    out.kv("Total spend (displayed)", f"${total:.4f}")
    out.info(f"Showing {len(display_logs)} of {len(logs)} logs")
