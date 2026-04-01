"""Dashboard command -- system overview."""

from __future__ import annotations

import time

import typer
from typing import Annotated

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_dashboard(ctx: AppContext) -> dict:
    c = ctx.client

    # Agent counts
    agents: list = []
    try:
        data = c.get("/agents/", params={"detail": "false"})
        agents = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    except Exception:
        pass

    online = sum(1 for a in agents if a.get("status") == "online")
    offline = len(agents) - online

    # Clients
    clients_count = 0
    try:
        data = c.get("/clients/")
        clients = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        clients_count = len(clients)
    except Exception:
        pass

    # Alerts
    alerts_count = 0
    try:
        data = c.patch("/alerts/", data={})
        alerts = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        alerts_count = len(alerts)
    except Exception:
        pass

    # Scripts
    scripts_count = 0
    try:
        data = c.get("/scripts/")
        scripts = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        scripts_count = len(scripts)
    except Exception:
        pass

    return {
        "agents_total": len(agents),
        "agents_online": online,
        "agents_offline": offline,
        "clients": clients_count,
        "alerts": alerts_count,
        "scripts": scripts_count,
    }


def _display_dashboard(ctx: AppContext, data: dict) -> None:
    out = ctx.output

    if out.json_mode:
        out.raw_json(data)
        return

    online = data["agents_online"]
    offline = data["agents_offline"]
    total = data["agents_total"]
    alerts = data["alerts"]

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Agents", [
            ("Total", str(total)),
            ("Online", f"[green]{online}[/green]"),
            ("Offline", f"[red]{offline}[/red]" if offline else "0"),
        ]),
        ("Resources", [
            ("Clients", str(data["clients"])),
            ("Active Alerts", f"[red]{alerts}[/red]" if alerts else "0"),
            ("Scripts", str(data["scripts"])),
        ]),
    ]

    out.detail("Tactical RMM Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Show system overview dashboard."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(actx)
                actx.output.console.clear()
                _display_dashboard(actx, data)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_dashboard(actx)
        _display_dashboard(actx, data)
