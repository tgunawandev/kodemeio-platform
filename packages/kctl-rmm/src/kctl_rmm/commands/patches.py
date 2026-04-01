"""Patch/update management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage Windows patches and updates.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """List pending patches for an agent."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/winupdate/{agent_id}/")

    patches = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for p in patches:
        severity = p.get("severity", "")
        sev_display = f"[red]{severity}[/red]" if "critical" in severity.lower() else severity
        rows.append([
            p.get("kb_article_ids", p.get("kb", "")),
            p.get("title", ""),
            sev_display,
            str(p.get("installed", False)),
        ])

    c.output.table(
        f"Patches ({len(patches)})",
        [("KB", "cyan"), ("Title", ""), ("Severity", ""), ("Installed", "")],
        rows,
        data_for_json=patches,
    )


@app.command()
def scan(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """Trigger a patch scan on an agent."""
    c: AppContext = ctx.obj
    c.client.post(f"/winupdate/{agent_id}/scan/")
    c.output.success(f"Patch scan triggered for {agent_id}")


@app.command()
def install(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    all_patches: Annotated[bool, typer.Option("--all", help="Install all pending patches")] = False,
    kb: Annotated[str | None, typer.Option("--kb", help="Specific KB article ID")] = None,
) -> None:
    """Install patches on an agent."""
    c: AppContext = ctx.obj

    if not all_patches and not kb:
        c.output.error("Specify --all or --kb KB_ID")
        raise typer.Exit(1)

    payload: dict = {}
    if kb:
        payload["kb_article_ids"] = [kb]

    c.client.post(f"/winupdate/{agent_id}/install/", data=payload)
    target = f"KB {kb}" if kb else "all pending patches"
    c.output.success(f"Patch install triggered for {agent_id}: {target}")
