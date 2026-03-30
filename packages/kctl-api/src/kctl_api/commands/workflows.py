"""Workflow commands for kctl-api.

Start, check status, and list workflows.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="workflows", help="Workflow management — start, status, list.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------
@app.command()
def start(
    ctx: typer.Context,
    workflow_name: Annotated[str, typer.Argument(help="Workflow name to start.")],
    data_json: Annotated[str | None, typer.Option("--data", "-d", help="JSON payload for the workflow.")] = None,
) -> None:
    """Start a new workflow run via POST /api/v1/workflows/start."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    payload: dict = {"name": workflow_name}
    if data_json:
        try:
            payload["data"] = json.loads(data_json)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

    try:
        result = actx.client.post("/api/v1/workflows/start", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Workflow started: {workflow_name}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Workflow run ID.")],
) -> None:
    """Check workflow run status via GET /api/v1/workflows/{run_id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"/api/v1/workflows/{run_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Workflow run not found: {run_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Workflow Run: {run_id}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_workflows(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List workflow runs via GET /api/v1/workflows."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get("/api/v1/workflows", params={"page": page, "per_page": per_page})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    total = len(items) if isinstance(data, list) else data.get("total", len(items)) if isinstance(data, dict) else 0

    rows: list[list[str]] = []
    for w in items:
        rows.append(
            [
                str(w.get("id", "")),
                w.get("name", ""),
                w.get("status", ""),
                str(w.get("created_at", "")),
            ]
        )

    out.table(
        title=f"Workflow Runs (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Status", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )
