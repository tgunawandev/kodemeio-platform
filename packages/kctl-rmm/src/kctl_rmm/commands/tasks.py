"""Automated task management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage automated tasks.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Filter by agent ID")] = None,
) -> None:
    """List automated tasks."""
    c: AppContext = ctx.obj
    params: dict = {}
    if agent:
        params["agent_id"] = agent

    data = c.client.get("/tasks/", params=params)
    tasks = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for t in tasks:
        enabled = "[green]yes[/green]" if t.get("enabled", False) else "[red]no[/red]"
        rows.append(
            [
                str(t.get("id", "")),
                t.get("name", ""),
                t.get("task_type", t.get("schedule", "")),
                enabled,
                str(t.get("agent", t.get("agent_id", ""))),
            ]
        )

    c.output.table(
        f"Tasks ({len(tasks)})",
        [("ID", "cyan"), ("Name", ""), ("Type/Schedule", ""), ("Enabled", ""), ("Agent", "dim")],
        rows,
        data_for_json=tasks,
    )


@app.command()
def run(
    ctx: typer.Context,
    task_id: Annotated[int, typer.Argument(help="Task ID to trigger")],
) -> None:
    """Trigger a task manually."""
    c: AppContext = ctx.obj
    c.client.post(f"/tasks/{task_id}/run/")
    c.output.success(f"Task {task_id} triggered")
