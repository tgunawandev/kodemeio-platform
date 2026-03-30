"""Automation template commands for kctl-api.

CRUD for automation templates and manual trigger execution.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(
    name="automation", help="Automation templates — list, create, update, delete, run.", no_args_is_help=True
)

_BASE = "/api/v1/automation/templates"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_templates(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List automation templates."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(_BASE, params={"page": page, "per_page": per_page})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for t in items:
        rows.append(
            [
                str(t.get("id", "")),
                t.get("name", ""),
                t.get("trigger_type", ""),
                "[green]yes[/green]" if t.get("enabled") else "[red]no[/red]",
                str(t.get("created_at", "")),
            ]
        )

    out.table(
        title=f"Automation Templates (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Trigger", ""),
            ("Enabled", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Template name.")],
    trigger_type: Annotated[str, typer.Option("--trigger", "-t", help="Trigger type (e.g. cron, webhook, event).")],
    config_json: Annotated[str | None, typer.Option("--config", "-c", help="JSON config payload.")] = None,
) -> None:
    """Create a new automation template via POST."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    payload: dict = {"name": name, "trigger_type": trigger_type}
    if config_json:
        try:
            payload["config"] = json.loads(config_json)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

    try:
        result = actx.client.post(_BASE, json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Template created: {name}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command(name="get")
def get_template(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Argument(help="Template ID.")],
) -> None:
    """Get automation template details."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/{template_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Template not found: {template_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Template: {data.get('name', template_id)}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command()
def update(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Argument(help="Template ID.")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name.")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable.")] = None,
    config_json: Annotated[str | None, typer.Option("--config", "-c", help="JSON config payload.")] = None,
) -> None:
    """Update an automation template via PATCH."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    payload: dict = {}
    if name:
        payload["name"] = name
    if enabled is not None:
        payload["enabled"] = enabled
    if config_json:
        try:
            payload["config"] = json.loads(config_json)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

    if not payload:
        out.warn("No fields to update.")
        raise typer.Exit(0)

    try:
        result = actx.client.patch(f"{_BASE}/{template_id}", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Template {template_id} updated.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command()
def delete(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Argument(help="Template ID.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete an automation template via DELETE."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(f"Delete template {template_id}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        result = actx.client.delete(f"{_BASE}/{template_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Template {template_id} deleted.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
@app.command()
def run(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Argument(help="Template ID to trigger.")],
    data_json: Annotated[str | None, typer.Option("--data", "-d", help="JSON input payload.")] = None,
) -> None:
    """Manually trigger an automation template via POST."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    payload: dict = {}
    if data_json:
        try:
            payload = json.loads(data_json)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

    try:
        result = actx.client.post(f"{_BASE}/{template_id}/run", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Template {template_id} triggered.")
    if actx.json_mode:
        out.raw_json(result)
