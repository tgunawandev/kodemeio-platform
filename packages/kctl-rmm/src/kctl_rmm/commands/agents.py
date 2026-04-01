"""Agent management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage Tactical RMM agents.")


def _status_icon(status: str) -> str:
    s = status.lower()
    if s == "online":
        return "[green]online[/green]"
    if s == "offline":
        return "[red]offline[/red]"
    return f"[yellow]{status}[/yellow]"


def _agent_status(agent: dict) -> str:
    if agent.get("status") == "online":
        return "online"
    return "offline"


@app.command("list")
def list_(
    ctx: typer.Context,
    detail: Annotated[bool, typer.Option("--detail", help="Full agent details")] = False,
    client: Annotated[Optional[str], typer.Option("--client", help="Filter by client name")] = None,
    site: Annotated[Optional[str], typer.Option("--site", help="Filter by site name")] = None,
) -> None:
    """List all agents."""
    c: AppContext = ctx.obj
    data = c.client.get("/agents/", params={"detail": str(detail).lower()})

    agents = data if isinstance(data, list) else data.get("results", data) if isinstance(data, dict) else []

    if client:
        agents = [a for a in agents if client.lower() in a.get("client_name", "").lower()]
    if site:
        agents = [a for a in agents if site.lower() in a.get("site_name", "").lower()]

    rows: list[list[str]] = []
    for a in agents:
        status = _agent_status(a)
        rows.append([
            a.get("agent_id", ""),
            a.get("hostname", ""),
            a.get("client_name", ""),
            a.get("site_name", ""),
            a.get("operating_system", a.get("plat", "")),
            _status_icon(status),
        ])

    c.output.table(
        f"Agents ({len(agents)})",
        [("Agent ID", "cyan"), ("Hostname", ""), ("Client", ""), ("Site", ""), ("OS", "dim"), ("Status", "")],
        rows,
        data_for_json=agents,
    )


@app.command()
def get(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """Get agent details."""
    c: AppContext = ctx.obj
    agent = c.client.get(f"/agents/{agent_id}/")

    if not isinstance(agent, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    status = _agent_status(agent)
    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Agent Info", [
            ("Agent ID", agent.get("agent_id", "")),
            ("Hostname", agent.get("hostname", "")),
            ("Client", agent.get("client_name", "")),
            ("Site", agent.get("site_name", "")),
            ("Status", _status_icon(status)),
            ("OS", agent.get("operating_system", "")),
            ("Version", agent.get("version", "")),
            ("Public IP", agent.get("public_ip", "")),
            ("Last Seen", agent.get("last_seen", "")),
        ]),
    ]

    # Hardware info if available
    hw_kvs: list[tuple[str, str]] = []
    if agent.get("total_ram"):
        hw_kvs.append(("RAM", f"{agent['total_ram']} GB"))
    if agent.get("cpu_model"):
        for cpu in agent.get("cpu_model", []):
            hw_kvs.append(("CPU", cpu))
    if agent.get("disks"):
        for disk in agent.get("disks", []):
            hw_kvs.append(("Disk", f"{disk.get('device', '')} {disk.get('total', '')}"))
    if hw_kvs:
        sections.append(("Hardware", hw_kvs))

    c.output.detail(f"Agent: {agent.get('hostname', agent_id)}", sections, data_for_json=agent)


@app.command()
def ping(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """Ping an agent to check connectivity."""
    c: AppContext = ctx.obj
    result = c.client.get(f"/agents/{agent_id}/ping/")

    if isinstance(result, dict):
        status = result.get("status", result.get("name", "unknown"))
    else:
        status = str(result)

    if "online" in str(status).lower() or status == "pong":
        c.output.success(f"Agent {agent_id} is reachable: {status}")
    else:
        c.output.error(f"Agent {agent_id} unreachable: {status}")
        raise typer.Exit(1)


@app.command()
def reboot(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Reboot a remote machine."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Reboot agent {agent_id}?"):
            raise typer.Exit(0)

    c.client.post(f"/agents/{agent_id}/reboot/")
    c.output.success(f"Reboot command sent to {agent_id}")


@app.command()
def update(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """Trigger agent update."""
    c: AppContext = ctx.obj
    c.client.post(f"/agents/{agent_id}/update/")
    c.output.success(f"Update triggered for {agent_id}")


@app.command()
def offline(ctx: typer.Context) -> None:
    """List agents that are offline/unreachable."""
    c: AppContext = ctx.obj
    data = c.client.get("/agents/", params={"detail": "false"})

    agents = data if isinstance(data, list) else data.get("results", data) if isinstance(data, dict) else []
    offline_agents = [a for a in agents if _agent_status(a) != "online"]

    rows: list[list[str]] = []
    for a in offline_agents:
        rows.append([
            a.get("agent_id", ""),
            a.get("hostname", ""),
            a.get("client_name", ""),
            a.get("site_name", ""),
            a.get("last_seen", ""),
        ])

    c.output.table(
        f"Offline Agents ({len(offline_agents)})",
        [("Agent ID", "cyan"), ("Hostname", ""), ("Client", ""), ("Site", ""), ("Last Seen", "dim")],
        rows,
        data_for_json=offline_agents,
    )


@app.command()
def summary(ctx: typer.Context) -> None:
    """Agent count summary by client/site, online/offline."""
    c: AppContext = ctx.obj
    data = c.client.get("/agents/", params={"detail": "false"})

    agents = data if isinstance(data, list) else data.get("results", data) if isinstance(data, dict) else []

    # Group by client
    clients: dict[str, dict[str, int]] = {}
    total_online = 0
    total_offline = 0

    for a in agents:
        client_name = a.get("client_name", "Unknown")
        site_name = a.get("site_name", "Unknown")
        key = f"{client_name} / {site_name}"
        if key not in clients:
            clients[key] = {"online": 0, "offline": 0}
        if _agent_status(a) == "online":
            clients[key]["online"] += 1
            total_online += 1
        else:
            clients[key]["offline"] += 1
            total_offline += 1

    rows: list[list[str]] = []
    for key, counts in sorted(clients.items()):
        total = counts["online"] + counts["offline"]
        rows.append([
            key,
            str(total),
            f"[green]{counts['online']}[/green]",
            f"[red]{counts['offline']}[/red]" if counts["offline"] else "0",
        ])

    rows.append(["[bold]TOTAL[/bold]", f"[bold]{len(agents)}[/bold]",
                  f"[bold green]{total_online}[/bold green]",
                  f"[bold red]{total_offline}[/bold red]" if total_offline else "[bold]0[/bold]"])

    c.output.table(
        "Agent Summary",
        [("Client / Site", "cyan"), ("Total", ""), ("Online", "green"), ("Offline", "red")],
        rows,
        data_for_json={"total": len(agents), "online": total_online, "offline": total_offline, "by_client_site": clients},
    )
