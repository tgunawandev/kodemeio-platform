"""Software inventory commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Software inventory management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """List installed software on an agent."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/software/{agent_id}/")

    software = (
        data
        if isinstance(data, list)
        else data.get("software", data.get("results", []))
        if isinstance(data, dict)
        else []
    )

    rows: list[list[str]] = []
    for s in software:
        rows.append(
            [
                s.get("name", ""),
                s.get("version", ""),
                s.get("publisher", s.get("vendor", "")),
                s.get("install_date", ""),
            ]
        )

    c.output.table(
        f"Installed Software ({len(software)})",
        [("Name", ""), ("Version", "cyan"), ("Publisher", "dim"), ("Install Date", "dim")],
        rows,
        data_for_json=software,
    )


@app.command()
def search(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Software name to search")],
    agent_id: Annotated[str | None, typer.Option("--agent", "-a", help="Limit to specific agent")] = None,
) -> None:
    """Search for software across agents."""
    c: AppContext = ctx.obj

    if agent_id:
        data = c.client.get(f"/software/{agent_id}/")
        software = (
            data
            if isinstance(data, list)
            else data.get("software", data.get("results", []))
            if isinstance(data, dict)
            else []
        )
        matches = [s for s in software if name.lower() in s.get("name", "").lower()]

        rows: list[list[str]] = []
        for s in matches:
            rows.append([agent_id, s.get("name", ""), s.get("version", "")])

        c.output.table(
            f"Software matching '{name}'",
            [("Agent", "cyan"), ("Name", ""), ("Version", "")],
            rows,
            data_for_json=matches,
        )
    else:
        # Get all agents, then search each
        agents_data = c.client.get("/agents/", params={"detail": "false"})
        agents = (
            agents_data
            if isinstance(agents_data, list)
            else agents_data.get("results", [])
            if isinstance(agents_data, dict)
            else []
        )

        rows = []
        all_matches: list[dict] = []
        for a in agents:
            aid = a.get("agent_id", "")
            try:
                data = c.client.get(f"/software/{aid}/")
                software = (
                    data
                    if isinstance(data, list)
                    else data.get("software", data.get("results", []))
                    if isinstance(data, dict)
                    else []
                )
                for s in software:
                    if name.lower() in s.get("name", "").lower():
                        rows.append([aid, a.get("hostname", ""), s.get("name", ""), s.get("version", "")])
                        all_matches.append({**s, "agent_id": aid, "hostname": a.get("hostname", "")})
            except Exception:
                continue

        c.output.table(
            f"Software matching '{name}' ({len(rows)} found)",
            [("Agent ID", "cyan"), ("Hostname", ""), ("Name", ""), ("Version", "")],
            rows,
            data_for_json=all_matches,
        )
