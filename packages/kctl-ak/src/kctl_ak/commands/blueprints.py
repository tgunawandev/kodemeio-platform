"""Blueprint management commands.

List, inspect, apply, and export Authentik blueprints.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Manage Authentik blueprints.")


@app.command()
def instances(ctx: typer.Context) -> None:
    """List all blueprint instances."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get_all("managed/blueprints/")
    except Exception as e:
        out.error(f"Failed to fetch blueprints: {e}")
        raise typer.Exit(code=1)

    rows: list[list[str]] = []
    for bp in data:
        bp_id = str(bp.get("pk", ""))
        name = bp.get("name", "")
        path = bp.get("path", "")
        bp_status = bp.get("status", "unknown")
        enabled = str(bp.get("enabled", False))
        last_applied = str(bp.get("last_applied", ""))

        if bp_status == "successful":
            status_display = "[green]OK[/green]"
        elif bp_status == "warning":
            status_display = "[yellow]WARN[/yellow]"
        elif bp_status == "error":
            status_display = "[red]ERROR[/red]"
        else:
            status_display = bp_status

        rows.append([bp_id[:8], name, path, status_display, enabled, last_applied])

    out.table(
        "Blueprint Instances",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Path", ""),
            ("Status", ""),
            ("Enabled", "dim"),
            ("Last Applied", "dim"),
        ],
        rows,
        data_for_json=data,
    )


@app.command()
def get(
    ctx: typer.Context,
    bp_id: Annotated[str, typer.Argument(help="Blueprint instance ID (UUID).")],
) -> None:
    """Show blueprint instance details."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        bp = c.get(f"managed/blueprints/{bp_id}/")
    except Exception as e:
        out.error(f"Failed to fetch blueprint: {e}")
        raise typer.Exit(code=1)

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    sections.append(
        (
            "Identity",
            [
                ("ID", str(bp.get("pk", ""))),
                ("Name", bp.get("name", "")),
                ("Path", bp.get("path", "")),
            ],
        )
    )
    sections.append(
        (
            "Status",
            [
                ("Status", bp.get("status", "unknown")),
                ("Enabled", str(bp.get("enabled", False))),
                ("Last Applied", str(bp.get("last_applied", ""))),
                ("Last Applied Hash", bp.get("last_applied_hash", "")),
            ],
        )
    )

    metadata = bp.get("metadata", {})
    if isinstance(metadata, dict) and metadata:
        meta_kvs: list[tuple[str, str]] = []
        for k, v in metadata.items():
            meta_kvs.append((k, str(v)))
        sections.append(("Metadata", meta_kvs))

    content = bp.get("content", "")
    if content:
        sections.append(
            ("Content", [("Preview", str(content)[:200] + "..." if len(str(content)) > 200 else str(content))])
        )

    out.detail(f"Blueprint: {bp.get('name', bp_id)}", sections, data_for_json=bp)


@app.command()
def apply(
    ctx: typer.Context,
    bp_id: Annotated[str, typer.Argument(help="Blueprint instance ID to apply.")],
) -> None:
    """Apply (or re-apply) a blueprint instance."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        c.post(f"managed/blueprints/{bp_id}/apply/")
        out.success(f"Blueprint '{bp_id}' applied successfully.")
    except Exception as e:
        out.error(f"Failed to apply blueprint: {e}")
        raise typer.Exit(code=1)


@app.command("export")
def export_(
    ctx: typer.Context,
    flow_slug: Annotated[str, typer.Argument(help="Flow slug to export as blueprint YAML.")],
) -> None:
    """Export a flow as a blueprint YAML file."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        resp = c.request("GET", f"flows/instances/{flow_slug}/export/")
        content = resp.text
    except Exception as e:
        out.error(f"Failed to export flow: {e}")
        raise typer.Exit(code=1)

    if out.json_mode:
        out.raw_json({"flow_slug": flow_slug, "content": content})
    else:
        out.header(f"Blueprint Export: {flow_slug}")
        out.text(content)
