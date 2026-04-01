"""Alert management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage alerts.")


@app.command("list")
def list_(
    ctx: typer.Context,
    severity: Annotated[Optional[str], typer.Option("--severity", "-s", help="Filter: info, warning, error")] = None,
) -> None:
    """List active alerts."""
    c: AppContext = ctx.obj
    params: dict = {}
    if severity:
        params["severity"] = severity

    data = c.client.patch("/alerts/", data=params or {})
    alerts = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for a in alerts:
        sev = a.get("severity", "")
        if sev == "error":
            sev_display = f"[red]{sev}[/red]"
        elif sev == "warning":
            sev_display = f"[yellow]{sev}[/yellow]"
        else:
            sev_display = sev
        rows.append([
            str(a.get("id", "")),
            a.get("agent", {}).get("hostname", a.get("agent_id", "")) if isinstance(a.get("agent"), dict) else str(a.get("agent", "")),
            a.get("alert_type", ""),
            sev_display,
            a.get("message", "")[:60],
            a.get("alert_time", a.get("created", "")),
        ])

    c.output.table(
        f"Alerts ({len(alerts)})",
        [("ID", "cyan"), ("Agent", ""), ("Type", ""), ("Severity", ""), ("Message", "dim"), ("Time", "dim")],
        rows,
        data_for_json=alerts,
    )


@app.command()
def dismiss(
    ctx: typer.Context,
    alert_id: Annotated[int, typer.Argument(help="Alert ID to dismiss")],
) -> None:
    """Dismiss an alert."""
    c: AppContext = ctx.obj
    c.client.delete(f"/alerts/{alert_id}/")
    c.output.success(f"Alert {alert_id} dismissed")
