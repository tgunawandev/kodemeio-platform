"""Model management commands for kctl-litellm.

List and inspect available models on the LiteLLM proxy.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Manage and inspect LiteLLM models.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available models via /v1/models."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        models = client.list_models()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not models:
        out.warn("No models found.")
        return

    table = Table(title="Available Models", show_header=True, header_style="bold cyan")
    table.add_column("Model ID", style="cyan")
    table.add_column("Object")
    table.add_column("Created")

    for model in models:
        model_id = model.get("id", "unknown") if isinstance(model, dict) else str(model)
        obj_type = model.get("object", "") if isinstance(model, dict) else ""
        created = str(model.get("created", "")) if isinstance(model, dict) else ""
        table.add_row(model_id, obj_type, created)

    rprint(table)
    out.info(f"Total models: {len(models)}")


@app.command()
def info(
    ctx: typer.Context,
    model: Annotated[
        str | None, typer.Argument(help="Model name to show info for (optional, shows all if omitted)")
    ] = None,
) -> None:
    """Show detailed model info with pricing via /model/info."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        models = client.model_info()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not models:
        out.warn("No model info available.")
        return

    # Filter to a specific model if requested
    if model:
        models = [
            m
            for m in models
            if isinstance(m, dict)
            and (m.get("model_name", "") == model or m.get("model_info", {}).get("id", "") == model)
        ]
        if not models:
            out.error(f"Model '{model}' not found.")
            raise typer.Exit(1)

    table = Table(title="Model Info", show_header=True, header_style="bold cyan")
    table.add_column("Model Name", style="cyan")
    table.add_column("Provider")
    table.add_column("Max Tokens", justify="right")
    table.add_column("Input $/1M", justify="right")
    table.add_column("Output $/1M", justify="right")

    for m in models:
        if not isinstance(m, dict):
            continue
        model_name = m.get("model_name", "unknown")
        litellm_params = m.get("litellm_params", {})
        model_info = m.get("model_info", {})

        provider = litellm_params.get("custom_llm_provider", "")
        if not provider:
            # Try to infer from model string
            litellm_model = litellm_params.get("model", "")
            provider = litellm_model.split("/")[0] if "/" in litellm_model else ""

        max_tokens = model_info.get("max_tokens", "")
        input_cost = model_info.get("input_cost_per_token", "")
        output_cost = model_info.get("output_cost_per_token", "")

        # Convert per-token cost to per-1M tokens
        input_display = f"${float(input_cost) * 1_000_000:.2f}" if input_cost else "[dim]-[/dim]"
        output_display = f"${float(output_cost) * 1_000_000:.2f}" if output_cost else "[dim]-[/dim]"

        table.add_row(
            model_name,
            provider,
            str(max_tokens) if max_tokens else "[dim]-[/dim]",
            input_display,
            output_display,
        )

    rprint(table)
    out.info(f"Total models: {len(models)}")
