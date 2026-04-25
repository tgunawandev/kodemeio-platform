"""Virtual key management commands for kctl-litellm.

Generate, inspect, update, and delete LiteLLM virtual keys.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Manage LiteLLM virtual keys.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


def _mask_key(key: str) -> str:
    """Mask a key, showing only first 8 and last 4 chars."""
    if not key:
        return "[dim]not set[/dim]"
    if len(key) <= 12:
        return "****"
    return f"{key[:8]}{'*' * (len(key) - 12)}{key[-4:]}"


@app.command()
def generate(
    ctx: typer.Context,
    team_id: Annotated[str | None, typer.Option("--team-id", help="Team ID to associate with the key.")] = None,
    max_budget: Annotated[float | None, typer.Option("--max-budget", help="Maximum budget in USD.")] = None,
    duration: Annotated[str | None, typer.Option("--duration", help="Key duration (e.g. 30d, 1h, 24h).")] = None,
    models: Annotated[str | None, typer.Option("--models", help="Comma-separated list of allowed models.")] = None,
    key_alias: Annotated[str | None, typer.Option("--key-alias", help="Alias for the key.")] = None,
) -> None:
    """Generate a new virtual key.

    Example: kctl-litellm keys generate --key-alias my-app --max-budget 100 --duration 30d
    """
    actx: AppContext = ctx.obj
    out = actx.output

    kwargs: dict = {}
    if team_id:
        kwargs["team_id"] = team_id
    if max_budget is not None:
        kwargs["max_budget"] = max_budget
    if duration:
        kwargs["duration"] = duration
    if models:
        kwargs["models"] = [m.strip() for m in models.split(",")]
    if key_alias:
        kwargs["key_alias"] = key_alias

    try:
        client = _get_client(actx)
        result = client.generate_key(**kwargs)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success("Virtual key generated")
    out.kv("Key", result.get("key", "[dim]unknown[/dim]"))
    out.kv("Token", result.get("token", "[dim]unknown[/dim]"))
    if result.get("key_alias"):
        out.kv("Alias", result["key_alias"])
    if result.get("max_budget"):
        out.kv("Max Budget", f"${result['max_budget']}")
    if result.get("duration"):
        out.kv("Duration", result["duration"])
    if result.get("models"):
        out.kv("Models", ", ".join(result["models"]))
    out.warn("Save the key now -- it cannot be retrieved later.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all virtual keys."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        keys = client.list_keys()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not keys:
        out.warn("No keys found.")
        return

    table = Table(title="Virtual Keys", show_header=True, header_style="bold cyan")
    table.add_column("Token", style="cyan")
    table.add_column("Alias")
    table.add_column("Team")
    table.add_column("Max Budget", justify="right")
    table.add_column("Spend", justify="right")
    table.add_column("Models")

    for k in keys:
        if not isinstance(k, dict):
            continue
        token = _mask_key(k.get("token", ""))
        alias = k.get("key_alias", "") or "[dim]-[/dim]"
        team = k.get("team_id", "") or "[dim]-[/dim]"
        budget = f"${k['max_budget']:.2f}" if k.get("max_budget") is not None else "[dim]-[/dim]"
        spend = f"${k['spend']:.4f}" if k.get("spend") is not None else "[dim]-[/dim]"
        model_list = ", ".join(k.get("models", [])) if k.get("models") else "[dim]all[/dim]"
        table.add_row(token, alias, team, budget, spend, model_list)

    rprint(table)
    out.info(f"Total keys: {len(keys)}")


@app.command()
def info(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key token or hash to inspect")],
) -> None:
    """Show detailed key information (key value masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        result = client.get_key_info(key)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    key_data = result.get("info", result) if isinstance(result, dict) else result

    if not isinstance(key_data, dict):
        out.error("Unexpected response format.")
        raise typer.Exit(1)

    out.kv("Token", _mask_key(key_data.get("token", "")))
    out.kv("Key Name", key_data.get("key_name", "[dim]-[/dim]"))
    out.kv("Key Alias", key_data.get("key_alias", "[dim]-[/dim]"))
    out.kv("Team ID", key_data.get("team_id", "[dim]-[/dim]"))
    out.kv("User ID", key_data.get("user_id", "[dim]-[/dim]"))

    if key_data.get("max_budget") is not None:
        out.kv("Max Budget", f"${key_data['max_budget']:.2f}")
    else:
        out.kv("Max Budget", "[dim]unlimited[/dim]")

    if key_data.get("spend") is not None:
        out.kv("Spend", f"${key_data['spend']:.4f}")

    if key_data.get("models"):
        out.kv("Models", ", ".join(key_data["models"]))
    else:
        out.kv("Models", "[dim]all[/dim]")

    if key_data.get("expires"):
        out.kv("Expires", key_data["expires"])
    if key_data.get("duration"):
        out.kv("Duration", key_data["duration"])


@app.command()
def update(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key token to update")],
    max_budget: Annotated[float | None, typer.Option("--max-budget", help="New maximum budget in USD.")] = None,
    models: Annotated[str | None, typer.Option("--models", help="Comma-separated list of allowed models.")] = None,
    key_alias: Annotated[str | None, typer.Option("--key-alias", help="New alias for the key.")] = None,
    duration: Annotated[str | None, typer.Option("--duration", help="New duration (e.g. 30d, 1h).")] = None,
) -> None:
    """Update a virtual key's settings."""
    actx: AppContext = ctx.obj
    out = actx.output

    kwargs: dict = {}
    if max_budget is not None:
        kwargs["max_budget"] = max_budget
    if models:
        kwargs["models"] = [m.strip() for m in models.split(",")]
    if key_alias:
        kwargs["key_alias"] = key_alias
    if duration:
        kwargs["duration"] = duration

    if not kwargs:
        out.error("No update options provided. Use --max-budget, --models, --key-alias, or --duration.")
        raise typer.Exit(1)

    try:
        client = _get_client(actx)
        result = client.update_key(key, **kwargs)
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Key updated: {_mask_key(key)}")


@app.command()
def delete(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key token to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a virtual key."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        if not typer.confirm(f"Delete key {_mask_key(key)}?"):
            raise typer.Exit(0)

    try:
        client = _get_client(actx)
        client.delete_key([key])
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Key deleted: {_mask_key(key)}")
