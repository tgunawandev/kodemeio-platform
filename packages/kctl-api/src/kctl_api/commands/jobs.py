"""Job queue management commands for kctl-api.

Monitor and manage ARQ background jobs.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="jobs", help="Background job management — overview, status, enqueue.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# overview
# ---------------------------------------------------------------------------
@app.command()
def overview(ctx: typer.Context) -> None:
    """Show job queue overview (GET /api/v1/jobs/queues/overview)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get("/api/v1/jobs/queues/overview")
    except AuthenticationError as e:
        out.error(f"Auth failed: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    if not data:
        out.info("No queue data available.")
        return

    # Display as table if data is a list of queues, or as detail if single dict
    if isinstance(data, list):
        rows: list[list[str]] = []
        for q in data:
            rows.append(
                [
                    q.get("name", ""),
                    str(q.get("queued", 0)),
                    str(q.get("active", 0)),
                    str(q.get("complete", 0)),
                    str(q.get("failed", 0)),
                ]
            )
        out.table(
            title="Job Queues Overview",
            columns=[
                ("Queue", "bold"),
                ("Queued", ""),
                ("Active", "yellow"),
                ("Complete", "green"),
                ("Failed", "red"),
            ],
            rows=rows,
            data_for_json=data,
        )
    else:
        sections: list[tuple[str, list[tuple[str, str]]]] = [
            ("Queue Stats", [(k, str(v)) for k, v in data.items()]),
        ]
        out.detail(title="Job Queues Overview", sections=sections, data_for_json=data)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID to check.")],
) -> None:
    """Get status of a specific job via GET /api/v1/jobs/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"/api/v1/jobs/{job_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Job not found: {job_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Job: {job_id}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------
@app.command()
def enqueue(
    ctx: typer.Context,
    function: Annotated[str, typer.Argument(help="Function name to enqueue.")],
    data_json: Annotated[str | None, typer.Option("--data", "-d", help="JSON payload for the job.")] = None,
) -> None:
    """Enqueue a new background job (admin-only) via POST /api/v1/jobs/enqueue."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    payload: dict = {"function": function}
    if data_json:
        try:
            payload["data"] = json.loads(data_json)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

    try:
        result = actx.client.post("/api/v1/jobs/enqueue", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Job enqueued: {function}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command(name="get")
def get_job(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID.")],
) -> None:
    """Get detailed job information via GET /api/v1/jobs/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"/api/v1/jobs/{job_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Job not found: {job_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Job: {job_id}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )
