"""Team management commands for kctl-litellm.

Create, list, update, and delete LiteLLM teams.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Manage LiteLLM teams.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command()
def create(
    ctx: typer.Context,
    team_alias: Annotated[str, typer.Option("--team-alias", help="Human-readable team alias.")],
    max_budget: Annotated[float | None, typer.Option("--max-budget", help="Maximum budget in USD.")] = None,
    models: Annotated[str | None, typer.Option("--models", help="Comma-separated list of allowed models.")] = None,
) -> None:
    """Create a new team.

    Example: kctl-litellm teams create --team-alias engineering --max-budget 500
    """
    actx: AppContext = ctx.obj
    out = actx.output

    kwargs: dict = {"team_alias": team_alias}
    if max_budget is not None:
        kwargs["max_budget"] = max_budget
    if models:
        kwargs["models"] = [m.strip() for m in models.split(",")]

    try:
        client = _get_client(actx)
        result = client.create_team(**kwargs)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success("Team created")
    out.kv("Team ID", result.get("team_id", "[dim]unknown[/dim]"))
    out.kv("Team Alias", result.get("team_alias", team_alias))
    if result.get("max_budget") is not None:
        out.kv("Max Budget", f"${result['max_budget']}")
    if result.get("models"):
        out.kv("Models", ", ".join(result["models"]))


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all teams."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        teams = client.list_teams()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not teams:
        out.warn("No teams found.")
        return

    table = Table(title="Teams", show_header=True, header_style="bold cyan")
    table.add_column("Team ID", style="cyan")
    table.add_column("Alias")
    table.add_column("Max Budget", justify="right")
    table.add_column("Spend", justify="right")
    table.add_column("Models")
    table.add_column("Members", justify="right")

    for t in teams:
        if not isinstance(t, dict):
            continue
        team_id = t.get("team_id", "unknown")
        alias = t.get("team_alias", "") or "[dim]-[/dim]"
        budget = f"${t['max_budget']:.2f}" if t.get("max_budget") is not None else "[dim]-[/dim]"
        spend = f"${t['spend']:.4f}" if t.get("spend") is not None else "[dim]-[/dim]"
        model_list = ", ".join(t.get("models", [])) if t.get("models") else "[dim]all[/dim]"
        members = str(len(t.get("members_with_roles", []))) if t.get("members_with_roles") else "0"
        table.add_row(team_id, alias, budget, spend, model_list, members)

    rprint(table)
    out.info(f"Total teams: {len(teams)}")


@app.command()
def update(
    ctx: typer.Context,
    team_id: Annotated[str, typer.Argument(help="Team ID to update")],
    team_alias: Annotated[str | None, typer.Option("--team-alias", help="New team alias.")] = None,
    max_budget: Annotated[float | None, typer.Option("--max-budget", help="New maximum budget in USD.")] = None,
    models: Annotated[str | None, typer.Option("--models", help="Comma-separated list of allowed models.")] = None,
) -> None:
    """Update a team's settings."""
    actx: AppContext = ctx.obj
    out = actx.output

    kwargs: dict = {}
    if team_alias:
        kwargs["team_alias"] = team_alias
    if max_budget is not None:
        kwargs["max_budget"] = max_budget
    if models:
        kwargs["models"] = [m.strip() for m in models.split(",")]

    if not kwargs:
        out.error("No update options provided. Use --team-alias, --max-budget, or --models.")
        raise typer.Exit(1)

    try:
        client = _get_client(actx)
        client.update_team(team_id, **kwargs)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Team '{team_id}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    team_id: Annotated[str, typer.Argument(help="Team ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a team."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        if not typer.confirm(f"Delete team '{team_id}'?"):
            raise typer.Exit(0)

    try:
        client = _get_client(actx)
        client.delete_team([team_id])
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Team '{team_id}' deleted")
