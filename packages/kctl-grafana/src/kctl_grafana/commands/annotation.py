"""Annotation commands for deploy markers and events."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Annotation management (deploy markers, events).")


@app.command("add")
def add_annotation(
    ctx: typer.Context,
    text: Annotated[str, typer.Argument(help="Annotation text")],
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Comma-separated tags")] = None,
    dashboard_uid: Annotated[str | None, typer.Option("--dashboard", help="Dashboard UID (global if omitted)")] = None,
) -> None:
    """Add an annotation (useful for deploy markers)."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    payload: dict = {
        "text": text,
        "time": int(time.time() * 1000),  # Grafana expects milliseconds
    }

    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",")]

    if dashboard_uid:
        # Resolve dashboard id from uid
        try:
            result = client.get(f"/dashboards/uid/{dashboard_uid}")
            dash_id = result.get("dashboard", {}).get("id")
            if dash_id:
                payload["dashboardId"] = dash_id
        except Exception:
            out.warn(f"Could not resolve dashboard '{dashboard_uid}', creating global annotation")

    result = client.post("/annotations", json_body=payload)
    out.success(f"Annotation created (id: {result.get('id', 'unknown')})")


@app.command("list")
def list_annotations(
    ctx: typer.Context,
    from_time: Annotated[
        str | None, typer.Option("--from", help="Start time (epoch ms or relative: 1h, 24h, 7d)")
    ] = None,
    to_time: Annotated[str | None, typer.Option("--to", help="End time (epoch ms or 'now')")] = None,
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Filter by tags (comma-separated)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 100,
) -> None:
    """List recent annotations."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    params: dict = {"limit": limit}

    if from_time:
        params["from"] = _parse_time(from_time)
    else:
        # Default: last 24h
        params["from"] = int((time.time() - 86400) * 1000)

    if to_time:
        params["to"] = _parse_time(to_time)
    else:
        params["to"] = int(time.time() * 1000)

    if tags:
        params["tags"] = tags

    annotations = client.get("/annotations", params=params)

    rows: list[list[str]] = []
    for a in annotations:
        ann_id = str(a.get("id", ""))
        text = a.get("text", "")[:60]
        ann_tags = ", ".join(a.get("tags", []))
        created = a.get("created", "")
        dashboard = a.get("dashboardUID", "global")
        rows.append([ann_id, text, ann_tags, dashboard, str(created)])

    out.table(
        f"Annotations ({len(annotations)})",
        [("ID", "cyan"), ("Text", ""), ("Tags", "dim"), ("Dashboard", "dim"), ("Created", "dim")],
        rows,
        data_for_json=annotations,
    )


def _parse_time(value: str) -> int:
    """Parse time value: epoch ms, or relative (1h, 24h, 7d)."""
    try:
        return int(value)
    except ValueError:
        pass

    now = time.time()
    if value == "now":
        return int(now * 1000)

    if value.endswith("h"):
        hours = int(value[:-1])
        return int((now - hours * 3600) * 1000)
    elif value.endswith("d"):
        days = int(value[:-1])
        return int((now - days * 86400) * 1000)
    elif value.endswith("m"):
        minutes = int(value[:-1])
        return int((now - minutes * 60) * 1000)

    return int(now * 1000)
