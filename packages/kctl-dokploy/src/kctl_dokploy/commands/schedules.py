"""Scheduled task management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage scheduled tasks (cron jobs).")


@app.command("list")
def list_(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument(help="Resource ID (compose, application, or server)")],
    schedule_type: Annotated[str, typer.Option("--type", "-t", help="Type: compose, application, server")] = "compose",
) -> None:
    """List scheduled tasks for a resource."""
    c: AppContext = ctx.obj
    params: dict = {"id": resource_id, "scheduleType": schedule_type}
    schedules = c.client.get("/schedule.list", params=params)
    if not isinstance(schedules, list):
        schedules = []
    rows = []
    for s in schedules:
        sid = s.get("scheduleId", "")
        name = s.get("name", "")
        cron = s.get("cronExpression", "")
        command = s.get("command", "")[:40]
        stype = s.get("scheduleType", "")
        enabled = str(s.get("enabled", "-"))
        rows.append([sid, name, cron, command, stype, enabled])
    c.output.table(
        "Scheduled Tasks",
        [("ID", "dim"), ("Name", "cyan"), ("Cron", ""), ("Command", ""), ("Type", ""), ("Enabled", "")],
        rows,
        data_for_json=schedules,
    )


@app.command()
def get(
    ctx: typer.Context,
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID")],
) -> None:
    """Get schedule details."""
    c: AppContext = ctx.obj
    data = c.client.get("/schedule.one", params={"scheduleId": schedule_id})
    if not isinstance(data, dict):
        c.output.error(f"Schedule '{schedule_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Schedule",
            [
                ("ID", data.get("scheduleId", "")),
                ("Name", data.get("name", "")),
                ("Cron", data.get("cronExpression", "")),
                ("Command", data.get("command", "")),
                ("Type", data.get("scheduleType", "")),
                ("Shell", data.get("shell", "-")),
                ("Timezone", data.get("timezone", "-")),
                ("Enabled", str(data.get("enabled", "-"))),
                ("Application ID", data.get("applicationId", "-")),
                ("Compose ID", data.get("composeId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Schedule: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Schedule name")],
    cron: Annotated[str, typer.Option("--cron", help="Cron expression (e.g. '0 2 * * *')")],
    command: Annotated[str, typer.Option("--command", help="Command to execute")],
    schedule_type: Annotated[str, typer.Option("--type", "-t", help="Type: compose, application, server")] = "compose",
    compose: Annotated[str | None, typer.Option("--compose", "-c", help="Compose service ID")] = None,
    service_name: Annotated[
        str | None, typer.Option("--service", help="Service name in compose (e.g. 'postgres')")
    ] = None,
    application: Annotated[str | None, typer.Option("--application", "-a", help="Application ID")] = None,
    server_id: Annotated[str | None, typer.Option("--server", help="Server ID")] = None,
    shell_type: Annotated[str, typer.Option("--shell", help="Shell: bash or sh")] = "bash",
    timezone: Annotated[str | None, typer.Option("--timezone", help="Timezone (e.g. 'Asia/Jakarta')")] = None,
) -> None:
    """Create a new scheduled task on a compose, application, or server."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "cronExpression": cron,
        "command": command,
        "scheduleType": schedule_type,
        "shellType": shell_type,
    }
    if compose:
        payload["composeId"] = compose
    if service_name:
        payload["serviceName"] = service_name
    if application:
        payload["applicationId"] = application
    if server_id:
        payload["serverId"] = server_id
    if timezone:
        payload["timezone"] = timezone
    result = c.client.post("/schedule.create", json=payload)
    sid = result.get("scheduleId", "") if isinstance(result, dict) else ""
    c.output.success(f"Schedule '{name}' created: {sid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    cron: Annotated[str | None, typer.Option("--cron", help="New cron expression")] = None,
    command: Annotated[str | None, typer.Option("--command", help="New command")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
) -> None:
    """Update a scheduled task."""
    c: AppContext = ctx.obj
    payload: dict = {"scheduleId": schedule_id}
    if name is not None:
        payload["name"] = name
    if cron is not None:
        payload["cronExpression"] = cron
    if command is not None:
        payload["command"] = command
    if enabled is not None:
        payload["enabled"] = enabled
    if len(payload) == 1:
        c.output.error("Nothing to update. Provide at least one option.")
        raise typer.Exit(1)
    result = c.client.post("/schedule.update", json=payload)
    c.output.success(f"Schedule '{schedule_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a scheduled task (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete schedule '{schedule_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/schedule.delete", json={"scheduleId": schedule_id})
    c.output.success(f"Schedule '{schedule_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def run(
    ctx: typer.Context,
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID to run")],
) -> None:
    """Manually run a scheduled task."""
    c: AppContext = ctx.obj
    result = c.client.post("/schedule.runManually", json={"scheduleId": schedule_id})
    c.output.success("Scheduled task executed")
    if c.json_mode:
        c.output.raw_json(result)
