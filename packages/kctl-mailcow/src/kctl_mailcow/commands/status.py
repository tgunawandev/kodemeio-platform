"""Status and health check commands."""

from __future__ import annotations

import time

import typer
from typing import Annotated

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Server status and health.")


def _fetch_status(ctx: AppContext) -> dict:
    """Collect container status data."""
    c = ctx.client

    containers = {}
    try:
        data = c.mc_get("status/containers")
        if isinstance(data, dict):
            containers = data
    except Exception:
        pass

    vmail = {}
    try:
        data = c.mc_get("status/vmail")
        if isinstance(data, dict):
            vmail = data
    except Exception:
        pass

    solr = {}
    try:
        data = c.mc_get("status/solr")
        if isinstance(data, dict):
            solr = data
    except Exception:
        pass

    return {
        "containers": containers,
        "vmail": vmail,
        "solr": solr,
    }


@app.callback(invoke_without_command=True)
def status(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Show Mailcow container and service status."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_status(actx)
                actx.output.console.clear()
                _display_status(actx, data)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_status(actx)
        _display_status(actx, data)


def _display_status(ctx: AppContext, data: dict) -> None:
    out = ctx.output

    if ctx.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Container status
    containers = data.get("containers", {})
    if containers:
        container_kvs: list[tuple[str, str]] = []
        for name, info in containers.items():
            if isinstance(info, dict):
                state = info.get("state", "unknown")
                if state == "running":
                    container_kvs.append((name, f"[green]{state}[/green]"))
                else:
                    container_kvs.append((name, f"[red]{state}[/red]"))
            else:
                state_str = str(info)
                if state_str == "running":
                    container_kvs.append((name, f"[green]{state_str}[/green]"))
                else:
                    container_kvs.append((name, f"[red]{state_str}[/red]"))
        sections.append(("Containers", container_kvs))
    else:
        sections.append(("Containers", [("Status", "[red]Unable to fetch[/red]")]))

    # Vmail status
    vmail = data.get("vmail", {})
    if vmail:
        sections.append(
            (
                "Vmail Storage",
                [
                    ("Used", str(vmail.get("used_percent", "unknown"))),
                    ("Total", str(vmail.get("total", "unknown"))),
                ],
            )
        )

    # Solr status
    solr = data.get("solr", {})
    if solr:
        sections.append(
            (
                "Solr (FTS)",
                [
                    ("Enabled", str(solr.get("enabled", False))),
                    ("Documents", str(solr.get("documents", 0))),
                    ("Size", str(solr.get("size", "unknown"))),
                ],
            )
        )

    out.detail("Mailcow Status", sections, data_for_json=data)
