"""Team info commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import TEAM_SHOW_QUERY, TEAMS_LIST_QUERY

app = typer.Typer(help="Team information.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all teams with member counts."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(TEAMS_LIST_QUERY)
    teams = data.get("teams", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(teams)
        return

    if not teams:
        out.info("No teams found")
        return

    rows = [
        [
            t.get("key", ""),
            t.get("name", ""),
            str(len(t.get("members", {}).get("nodes", []))),
            t.get("timezone", ""),
        ]
        for t in teams
    ]
    out.table(
        f"Teams ({len(teams)})",
        [("Key", "cyan"), ("Name", "white"), ("Members", "yellow"), ("Timezone", "green")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    team_id: Annotated[str, typer.Argument(help="Team ID (UUID) or key")],
) -> None:
    """Show team members, workflow states, and labels."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(TEAM_SHOW_QUERY, {"id": team_id})
    team = data.get("team", {})

    if out.json_mode:
        out.raw_json(team)
        return

    members = team.get("members", {}).get("nodes", [])
    states = team.get("states", {}).get("nodes", [])
    labels = team.get("labels", {}).get("nodes", [])

    sections = [
        (
            "Team",
            [
                ("Key", team.get("key", "")),
                ("Name", team.get("name", "")),
                ("Description", team.get("description") or "-"),
                ("Timezone", team.get("timezone", "")),
                ("Members", str(len(members))),
            ],
        ),
    ]
    out.detail(team.get("name", "Team"), sections)

    if members:
        rows = [[m.get("name", ""), m.get("email", ""), str(m.get("active", True))] for m in members]
        out.table("Members", [("Name", "cyan"), ("Email", "white"), ("Active", "green")], rows)

    if states:
        rows = [
            [s.get("name", ""), s.get("type", ""), s.get("color", "")]
            for s in sorted(states, key=lambda s: s.get("position", 0))
        ]
        out.table("Workflow States", [("Name", "cyan"), ("Type", "white"), ("Color", "yellow")], rows)

    if labels:
        rows = [[lbl.get("name", ""), lbl.get("color", "")] for lbl in labels]
        out.table("Labels", [("Name", "cyan"), ("Color", "yellow")], rows)
