"""Dashboard management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Dashboard management.")


@app.command("list")
def list_dashboards(ctx: typer.Context) -> None:
    """List all dashboards."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})

    rows: list[list[str]] = []
    for d in dashboards:
        uid = d.get("uid", "")
        title = d.get("title", "")
        folder = d.get("folderTitle", "General")
        tags = ", ".join(d.get("tags", []))
        starred = "[yellow]*[/yellow]" if d.get("isStarred") else ""
        rows.append([uid, title, folder, tags, starred])

    out.table(
        f"Dashboards ({len(dashboards)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Tags", "dim"), ("Starred", "")],
        rows,
        data_for_json=dashboards,
    )


@app.command("show")
def show_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
) -> None:
    """Show dashboard metadata and panel summary."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    result = client.get(f"/dashboards/uid/{uid}")
    meta = result.get("meta", {})
    dashboard = result.get("dashboard", {})
    panels = dashboard.get("panels", [])

    sections = [
        (
            "Dashboard",
            [
                ("UID", dashboard.get("uid", "")),
                ("Title", dashboard.get("title", "")),
                ("Version", str(dashboard.get("version", 0))),
                ("Created", meta.get("created", "")),
                ("Updated", meta.get("updated", "")),
                ("Created by", meta.get("createdBy", "")),
                ("Updated by", meta.get("updatedBy", "")),
                ("Folder", meta.get("folderTitle", "General")),
                ("URL", meta.get("url", "")),
            ],
        ),
        (
            f"Panels ({len(panels)})",
            [(p.get("title", "Untitled"), p.get("type", "unknown")) for p in panels],
        ),
    ]

    out.detail(
        f"Dashboard: {dashboard.get('title', uid)}",
        sections,
        data_for_json=result,
    )


@app.command("export")
def export_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    output_file: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export dashboard JSON to file."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    result = client.get(f"/dashboards/uid/{uid}")
    dashboard = result.get("dashboard", {})
    title = dashboard.get("title", uid).replace(" ", "-").replace("/", "-").lower()

    if output_file is None:
        output_file = f"{title}-{uid}.json"

    # Clean for export (remove id so it can be imported fresh)
    export_data = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": "Exported from kctl-grafana",
    }
    # Remove the internal id for portability
    export_data["dashboard"].pop("id", None)

    path = Path(output_file)
    path.write_text(json.dumps(export_data, indent=2))
    out.success(f"Dashboard exported to {path}")


@app.command("import")
def import_dashboard(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="JSON file to import")],
    folder_uid: Annotated[str | None, typer.Option("--folder", help="Target folder UID")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing")] = True,
) -> None:
    """Import dashboard from JSON file."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    path = Path(file_path)
    if not path.exists():
        out.error(f"File not found: {path}")
        raise typer.Exit(1)

    data = json.loads(path.read_text())

    # Handle both raw dashboard JSON and export format
    payload = data if "dashboard" in data else {"dashboard": data}

    payload["overwrite"] = overwrite
    if folder_uid:
        payload["folderUid"] = folder_uid

    # Remove id for fresh import
    payload.get("dashboard", {}).pop("id", None)

    result = client.post("/dashboards/db", json_body=payload)
    out.success(f"Dashboard imported: {result.get('slug', 'unknown')} (uid: {result.get('uid', 'unknown')})")
    out.kv("URL", result.get("url", ""))


@app.command("search")
def search_dashboards(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
) -> None:
    """Search dashboards by name or tag."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    results = client.get("/search", params={"query": query, "type": "dash-db"})

    rows: list[list[str]] = []
    for d in results:
        uid = d.get("uid", "")
        title = d.get("title", "")
        folder = d.get("folderTitle", "General")
        tags = ", ".join(d.get("tags", []))
        rows.append([uid, title, folder, tags])

    out.table(
        f"Search results for '{query}' ({len(results)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Tags", "dim")],
        rows,
        data_for_json=results,
    )


@app.command("star")
def star_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    unstar: Annotated[bool, typer.Option("--unstar", help="Remove star")] = False,
) -> None:
    """Star or unstar a dashboard."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # First get the dashboard id from uid
    result = client.get(f"/dashboards/uid/{uid}")
    dash_id = result.get("dashboard", {}).get("id")

    if not dash_id:
        out.error(f"Dashboard not found: {uid}")
        raise typer.Exit(1)

    if unstar:
        client.delete(f"/user/stars/dashboard/{dash_id}")
        out.success(f"Unstarred dashboard {uid}")
    else:
        client.post(f"/user/stars/dashboard/{dash_id}", json_body={})
        out.success(f"Starred dashboard {uid}")
