"""Script management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage and execute scripts.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all scripts."""
    c: AppContext = ctx.obj
    data = c.client.get("/scripts/")

    scripts = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for s in scripts:
        rows.append(
            [
                str(s.get("id", "")),
                s.get("name", ""),
                s.get("shell", ""),
                s.get("script_type", ""),
                s.get("description", "")[:60],
            ]
        )

    c.output.table(
        f"Scripts ({len(scripts)})",
        [("ID", "cyan"), ("Name", ""), ("Shell", ""), ("Type", "dim"), ("Description", "dim")],
        rows,
        data_for_json=scripts,
    )


@app.command()
def get(
    ctx: typer.Context,
    script_id: Annotated[int, typer.Argument(help="Script ID")],
) -> None:
    """Get script details."""
    c: AppContext = ctx.obj
    script = c.client.get(f"/scripts/{script_id}/")

    if not isinstance(script, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Script Info",
            [
                ("ID", str(script.get("id", ""))),
                ("Name", script.get("name", "")),
                ("Shell", script.get("shell", "")),
                ("Type", script.get("script_type", "")),
                ("Description", script.get("description", "")),
                ("Default Timeout", str(script.get("default_timeout", ""))),
                ("Args", str(script.get("args", []))),
            ],
        ),
    ]

    body = script.get("script_body", "")
    if body:
        sections.append(("Script Body (first 20 lines)", [("", line) for line in body.split("\n")[:20]]))

    c.output.detail(f"Script: {script.get('name', script_id)}", sections, data_for_json=script)


@app.command()
def run(
    ctx: typer.Context,
    script_id: Annotated[int, typer.Argument(help="Script ID")],
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Agent ID")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Run on all agents")] = False,
    client_filter: Annotated[str | None, typer.Option("--client", help="Run on all agents in client")] = None,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Script timeout in seconds")] = 120,
) -> None:
    """Run a script on agent(s). Uses fire-and-forget mode."""
    c: AppContext = ctx.obj

    if not agent and not all_agents and not client_filter:
        c.output.error("Specify --agent, --all, or --client")
        raise typer.Exit(1)

    target_agents: list[str] = []

    if agent:
        target_agents = [agent]
    else:
        data = c.client.get("/agents/", params={"detail": "false"})
        agents_list = data if isinstance(data, list) else data.get("results", data) if isinstance(data, dict) else []

        if client_filter:
            agents_list = [a for a in agents_list if client_filter.lower() in a.get("client_name", "").lower()]

        target_agents = [a["agent_id"] for a in agents_list if a.get("status") == "online"]

    if not target_agents:
        c.output.warn("No target agents found")
        return

    c.output.info(f"Running script {script_id} on {len(target_agents)} agent(s) (fire-and-forget)")

    success = 0
    failed = 0
    for aid in target_agents:
        try:
            c.client.post(
                f"/agents/{aid}/runscript/",
                data={
                    "script": script_id,
                    "output": "forget",
                    "timeout": timeout,
                },
            )
            success += 1
        except Exception as e:
            c.output.warn(f"Failed on {aid}: {e}")
            failed += 1

    c.output.success(f"Script dispatched: {success} ok, {failed} failed")


@app.command()
def history(
    ctx: typer.Context,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Filter by agent ID")] = None,
) -> None:
    """View script execution history."""
    c: AppContext = ctx.obj
    params: dict = {}
    if agent:
        params["agent_id"] = agent

    data = c.client.get("/agents/history/", params=params)

    entries = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for e in entries[:50]:
        retcode = e.get("retcode", "")
        status = "[green]OK[/green]" if retcode == 0 else f"[red]rc={retcode}[/red]"
        rows.append(
            [
                str(e.get("id", "")),
                e.get("agent_id", e.get("agent", "")),
                e.get("script_name", e.get("script", "")),
                str(e.get("execution_time", "")),
                status,
            ]
        )

    c.output.table(
        f"Script History ({len(entries)} entries)",
        [("ID", "cyan"), ("Agent", ""), ("Script", ""), ("Exec Time", "dim"), ("Status", "")],
        rows,
        data_for_json=entries[:50],
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Script name")],
    shell: Annotated[str, typer.Option("--shell", "-s", help="Shell type: bash, powershell, python")] = "powershell",
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Script file path")] = None,
    description: Annotated[str, typer.Option("--description", "-d", help="Script description")] = "",
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Default timeout")] = 120,
) -> None:
    """Upload a new script."""
    c: AppContext = ctx.obj

    if not file:
        c.output.error("--file is required")
        raise typer.Exit(1)

    if not file.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)

    script_body = file.read_text()

    result = c.client.post(
        "/scripts/",
        data={
            "name": name,
            "shell": shell,
            "script_body": script_body,
            "description": description,
            "default_timeout": timeout,
        },
    )

    if isinstance(result, dict):
        c.output.success(f"Script created: {result.get('name', name)} (ID: {result.get('id', 'unknown')})")
    else:
        c.output.success(f"Script created: {name}")
