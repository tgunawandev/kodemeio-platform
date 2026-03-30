"""Status overview command."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Quick status overview.")


@app.command("overview")
def overview(ctx: typer.Context) -> None:
    """Show Grafana status overview: dashboard count, datasource health, active alerts, version."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # Gather data
    health = client.check_health()
    version = health.get("version", "unknown")

    dashboard_count = 0
    datasource_count = 0
    alert_count = 0

    try:
        dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})
        dashboard_count = len(dashboards)
    except Exception:
        pass

    try:
        datasources = client.get("/datasources")
        datasource_count = len(datasources)
    except Exception:
        pass

    try:
        alerts = client.get("/v1/provisioning/alert-rules")
        alert_count = len(alerts)
    except Exception:
        pass

    # Count firing alerts
    firing_count = 0
    try:
        alert_instances = client.get("/alertmanager/grafana/api/v2/alerts")
        firing_count = sum(1 for a in alert_instances if a.get("status", {}).get("state") == "active")
    except Exception:
        pass

    db_status = health.get("database", "unknown")
    db_display = "[green]ok[/green]" if db_status == "ok" else f"[red]{db_status}[/red]"
    firing_display = f"[red]{firing_count}[/red]" if firing_count > 0 else "[green]0[/green]"

    sections = [
        (
            "Grafana Status",
            [
                ("Version", version),
                ("Database", db_display),
                ("Dashboards", str(dashboard_count)),
                ("Datasources", str(datasource_count)),
                ("Alert rules", str(alert_count)),
                ("Firing alerts", firing_display),
            ],
        ),
    ]

    out.detail(
        "Status Overview",
        sections,
        data_for_json={
            "version": version,
            "database": db_status,
            "dashboards": dashboard_count,
            "datasources": datasource_count,
            "alert_rules": alert_count,
            "firing_alerts": firing_count,
        },
    )
