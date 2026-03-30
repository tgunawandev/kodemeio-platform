"""Cycle (sprint) management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import (
    CYCLE_CURRENT_QUERY,
    CYCLE_SHOW_QUERY,
    CYCLES_LIST_QUERY,
)

app = typer.Typer(help="Cycle (sprint) management.")


@app.command()
def current(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """Show current active cycle with progress and issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLE_CURRENT_QUERY, {"teamKey": team_key})
    cycles = data.get("cycles", {}).get("nodes", [])

    if not cycles:
        out.info("No active cycle")
        return

    cycle = cycles[0]

    if out.json_mode:
        out.raw_json(cycle)
        return

    progress = cycle.get("progress", 0)
    progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)

    sections = [
        (
            "Current Cycle",
            [
                ("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}"),
                ("Progress", progress_pct),
                ("Starts", (cycle.get("startsAt") or "")[:10]),
                ("Ends", (cycle.get("endsAt") or "")[:10]),
            ],
        ),
    ]
    out.detail("Active Cycle", sections)

    issues = cycle.get("issues", {}).get("nodes", [])
    if issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:50],
                str(issue.get("priority", "-")),
                issue.get("state", {}).get("name", ""),
                (issue.get("assignee") or {}).get("name", ""),
            ]
            for issue in issues
        ]
        out.table(
            f"Cycle Issues ({len(issues)})",
            [("ID", "cyan"), ("Title", "white"), ("P", "yellow"), ("State", "green"), ("Assignee", "magenta")],
            rows,
        )


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List past and upcoming cycles."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLES_LIST_QUERY, {"teamKey": team_key, "first": limit})
    cycles = data.get("cycles", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(cycles)
        return

    if not cycles:
        out.info("No cycles found")
        return

    rows = [
        [
            str(c.get("number", "")),
            c.get("name") or f"Cycle {c.get('number', '?')}",
            (c.get("startsAt") or "")[:10],
            (c.get("endsAt") or "")[:10],
            f"{(c.get('progress', 0) or 0) * 100:.0f}%",
        ]
        for c in cycles
    ]
    out.table(
        f"Cycles ({len(cycles)})",
        [("Num", "cyan"), ("Name", "white"), ("Start", "yellow"), ("End", "yellow"), ("Progress", "green")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    cycle_id: Annotated[str, typer.Argument(help="Cycle ID (UUID)")],
) -> None:
    """Show cycle details: scope, completed, remaining issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(CYCLE_SHOW_QUERY, {"id": cycle_id})
    cycle = data.get("cycle", {})

    if out.json_mode:
        out.raw_json(cycle)
        return

    progress = cycle.get("progress", 0)
    progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)
    issues = cycle.get("issues", {}).get("nodes", [])

    sections = [
        (
            "Cycle Details",
            [
                ("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}"),
                ("Number", str(cycle.get("number", ""))),
                ("Progress", progress_pct),
                ("Starts", (cycle.get("startsAt") or "")[:10]),
                ("Ends", (cycle.get("endsAt") or "")[:10]),
                ("Total Issues", str(len(issues))),
            ],
        ),
    ]
    out.detail(f"Cycle {cycle.get('number', '?')}", sections)

    if issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:50],
                issue.get("state", {}).get("name", ""),
                (issue.get("assignee") or {}).get("name", ""),
                str(issue.get("estimate") or "-"),
            ]
            for issue in issues
        ]
        out.table(
            "",
            [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta"), ("Est", "yellow")],
            rows,
        )


@app.command()
def stats(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """Show velocity trends across recent cycles."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLES_LIST_QUERY, {"teamKey": team_key, "first": 10})
    cycles = data.get("cycles", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json({"cycles": len(cycles), "data": cycles})
        return

    if not cycles:
        out.info("No cycles found for velocity analysis")
        return

    out.header("Velocity Trends (last 10 cycles)")
    rows = [
        [
            str(c.get("number", "")),
            c.get("name") or f"Cycle {c.get('number', '?')}",
            f"{(c.get('progress', 0) or 0) * 100:.0f}%",
            (c.get("startsAt") or "")[:10],
            (c.get("endsAt") or "")[:10],
        ]
        for c in cycles
    ]
    out.table(
        "",
        [("Num", "cyan"), ("Name", "white"), ("Completion", "green"), ("Start", "yellow"), ("End", "yellow")],
        rows,
    )
