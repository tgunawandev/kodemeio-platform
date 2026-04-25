"""Budget management commands for kctl-litellm.

Create and list LiteLLM budgets.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Manage LiteLLM budgets.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command()
def create(
    ctx: typer.Context,
    budget_id: Annotated[str | None, typer.Option("--budget-id", help="Budget identifier.")] = None,
    max_budget: Annotated[float, typer.Option("--max-budget", help="Maximum budget in USD.")] = 100.0,
    soft_budget: Annotated[
        float | None, typer.Option("--soft-budget", help="Soft budget limit (warning threshold).")
    ] = None,
    max_parallel_requests: Annotated[
        int | None, typer.Option("--max-parallel-requests", help="Max parallel requests.")
    ] = None,
    tpm_limit: Annotated[int | None, typer.Option("--tpm-limit", help="Tokens per minute limit.")] = None,
    rpm_limit: Annotated[int | None, typer.Option("--rpm-limit", help="Requests per minute limit.")] = None,
) -> None:
    """Create a new budget.

    Example: kctl-litellm budgets create --budget-id dev-budget --max-budget 200
    """
    actx: AppContext = ctx.obj
    out = actx.output

    kwargs: dict = {"max_budget": max_budget}
    if budget_id:
        kwargs["budget_id"] = budget_id
    if soft_budget is not None:
        kwargs["soft_budget"] = soft_budget
    if max_parallel_requests is not None:
        kwargs["max_parallel_requests"] = max_parallel_requests
    if tpm_limit is not None:
        kwargs["tpm_limit"] = tpm_limit
    if rpm_limit is not None:
        kwargs["rpm_limit"] = rpm_limit

    try:
        client = _get_client(actx)
        result = client.create_budget(**kwargs)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success("Budget created")
    out.kv("Budget ID", result.get("budget_id", "[dim]auto-generated[/dim]"))
    out.kv("Max Budget", f"${result.get('max_budget', max_budget)}")
    if result.get("soft_budget") is not None:
        out.kv("Soft Budget", f"${result['soft_budget']}")
    if result.get("tpm_limit"):
        out.kv("TPM Limit", str(result["tpm_limit"]))
    if result.get("rpm_limit"):
        out.kv("RPM Limit", str(result["rpm_limit"]))


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all budgets."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        budgets = client.list_budgets()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not budgets:
        out.warn("No budgets found.")
        return

    table = Table(title="Budgets", show_header=True, header_style="bold cyan")
    table.add_column("Budget ID", style="cyan")
    table.add_column("Max Budget", justify="right")
    table.add_column("Soft Budget", justify="right")
    table.add_column("TPM Limit", justify="right")
    table.add_column("RPM Limit", justify="right")
    table.add_column("Max Parallel", justify="right")

    for b in budgets:
        if not isinstance(b, dict):
            continue
        budget_id = b.get("budget_id", "unknown")
        max_b = f"${b['max_budget']:.2f}" if b.get("max_budget") is not None else "[dim]-[/dim]"
        soft_b = f"${b['soft_budget']:.2f}" if b.get("soft_budget") is not None else "[dim]-[/dim]"
        tpm = str(b.get("tpm_limit", "")) or "[dim]-[/dim]"
        rpm = str(b.get("rpm_limit", "")) or "[dim]-[/dim]"
        max_par = str(b.get("max_parallel_requests", "")) or "[dim]-[/dim]"
        table.add_row(budget_id, max_b, soft_b, tpm, rpm, max_par)

    rprint(table)
    out.info(f"Total budgets: {len(budgets)}")
