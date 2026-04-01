"""Automated checks management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage automated checks.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent: Annotated[Optional[str], typer.Option("--agent", help="Filter by agent ID")] = None,
) -> None:
    """List automated checks."""
    c: AppContext = ctx.obj

    if agent:
        data = c.client.get(f"/checks/{agent}/")
    else:
        data = c.client.get("/checks/")

    checks = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if not checks:
        c.output.info("No automated checks found.")
        return

    rows: list[list[str]] = []
    for ch in checks:
        status = ch.get("status", "")
        if status == "passing":
            status_str = "[green]passing[/green]"
        elif status == "failing":
            status_str = "[red]failing[/red]"
        else:
            status_str = f"[yellow]{status}[/yellow]"

        rows.append(
            [
                str(ch.get("id", "")),
                ch.get("readable_desc", ch.get("name", "")),
                ch.get("check_type", ""),
                status_str,
                ch.get("agent", {}).get("hostname", ch.get("agent_id", "-"))
                if isinstance(ch.get("agent"), dict)
                else str(ch.get("agent", "-")),
                str(ch.get("alert_severity", "-")),
            ]
        )

    c.output.table(
        f"Automated Checks ({len(checks)})",
        [("ID", "dim"), ("Description", "cyan"), ("Type", ""), ("Status", ""), ("Agent", ""), ("Severity", "dim")],
        rows,
        data_for_json=checks,
    )


@app.command()
def create(
    ctx: typer.Context,
    agent: Annotated[str, typer.Option("--agent", help="Agent ID")],
    check_type: Annotated[
        str, typer.Option("--type", help="Check type (diskspace, cpuload, memory, ping, winsvc, script, eventlog)")
    ],
    name: Annotated[str, typer.Option("--name", help="Check description/name")] = "",
    threshold: Annotated[
        Optional[int], typer.Option("--threshold", help="Threshold value (percent for disk/cpu/mem)")
    ] = None,
    alert_severity: Annotated[str, typer.Option("--severity", help="Alert severity: info, warning, error")] = "warning",
) -> None:
    """Create an automated check on an agent."""
    c: AppContext = ctx.obj

    payload: dict = {
        "agent": agent,
        "check_type": check_type,
        "alert_severity": alert_severity,
    }
    if name:
        payload["readable_desc"] = name
    if threshold is not None:
        payload["threshold"] = threshold

    # Different check types have different fields
    if check_type == "diskspace":
        payload.setdefault("threshold", 25)
        payload.setdefault("disk", "C:")
    elif check_type == "cpuload":
        payload.setdefault("threshold", 85)
    elif check_type == "memory":
        payload.setdefault("threshold", 85)

    result = c.client.post("/checks/", data=payload)

    check_id = ""
    if isinstance(result, dict):
        check_id = str(result.get("id", result.get("check_id", "")))

    c.output.success(f"Check created (type: {check_type})")
    if check_id:
        c.output.kv("Check ID", check_id)
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    check_id: Annotated[int, typer.Argument(help="Check ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an automated check."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete check {check_id}?"):
            raise typer.Exit(0)

    c.client.delete(f"/checks/{check_id}/")
    c.output.success(f"Check {check_id} deleted")


@app.command()
def results(
    ctx: typer.Context,
    check_id: Annotated[int, typer.Argument(help="Check ID")],
) -> None:
    """Show results/history for a check."""
    c: AppContext = ctx.obj

    data = c.client.get(f"/checks/{check_id}/history/")

    history = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if not history:
        c.output.info(f"No results for check {check_id}")
        return

    rows: list[list[str]] = []
    for h in history:
        status = h.get("status", "")
        if status == "passing":
            status_str = "[green]passing[/green]"
        elif status == "failing":
            status_str = "[red]failing[/red]"
        else:
            status_str = f"[yellow]{status}[/yellow]"

        rows.append(
            [
                str(h.get("id", "")),
                status_str,
                str(h.get("more_info", h.get("message", "-")))[:80],
                str(h.get("x", h.get("created_time", h.get("last_run", "-")))),
            ]
        )

    c.output.table(
        f"Check Results -- {check_id} ({len(history)})",
        [("ID", "dim"), ("Status", ""), ("Details", ""), ("Time", "dim")],
        rows,
        data_for_json=history,
    )


@app.command()
def run(
    ctx: typer.Context,
    check_id: Annotated[int, typer.Argument(help="Check ID to run")],
) -> None:
    """Manually run a check."""
    c: AppContext = ctx.obj

    result = c.client.post(f"/checks/{check_id}/run/")
    c.output.success(f"Check {check_id} triggered")
    if isinstance(result, dict) and c.output.json_mode:
        c.output.raw_json(result)
