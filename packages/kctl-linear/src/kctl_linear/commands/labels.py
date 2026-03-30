"""Label management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import LABEL_CREATE_MUTATION, LABELS_LIST_QUERY, TEAM_BY_KEY_QUERY

app = typer.Typer(help="Label management.")


def _resolve_team_id(ctx: AppContext, team_key: str) -> str:
    """Resolve a team key to its UUID."""
    data = ctx.client.query(TEAM_BY_KEY_QUERY, {"key": team_key})
    nodes = data.get("teams", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"Team '{team_key}' not found")
    return nodes[0]["id"]


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """List all labels, optionally filtered by team."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    variables: dict[str, str | None] = {}
    if team_key:
        variables["teamKey"] = team_key

    data = actx.client.query(LABELS_LIST_QUERY, variables)
    labels = data.get("issueLabels", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(labels)
        return

    if not labels:
        out.info("No labels found")
        return

    rows = [
        [
            lbl.get("name", ""),
            lbl.get("color", ""),
            (lbl.get("parent") or {}).get("name", "-"),
        ]
        for lbl in labels
    ]
    out.table(
        f"Labels ({len(labels)})",
        [("Name", "cyan"), ("Color", "yellow"), ("Parent", "white")],
        rows,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Label name")],
    color: Annotated[str | None, typer.Option("--color", "-c", help="Hex color (e.g., #ff0000)")] = None,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key (scoped label)")] = None,
) -> None:
    """Create a new label."""
    actx: AppContext = ctx.obj
    out = actx.output

    variables: dict[str, str | None] = {"name": name}
    if color:
        variables["color"] = color

    team_key = team or actx.default_team
    if team_key:
        variables["teamId"] = _resolve_team_id(actx, team_key)

    data = actx.client.query(LABEL_CREATE_MUTATION, variables)
    result = data.get("issueLabelCreate", {})
    label = result.get("issueLabel", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Created label '{label.get('name', name)}' ({label.get('color', '')})")
