"""Health check commands."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.core.config import resolve_active_profile_name

app = typer.Typer(help="Health checks for Grafana API.")


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Check Grafana API connectivity, version, and org info."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Checking profile '{active}'...")

    health = c.client.check_health()
    status = health.get("database", "unknown")

    if status == "ok":
        out.success(f"Grafana API reachable \u2014 v{health.get('version', 'unknown')}")
    else:
        out.error(f"Grafana health check failed: {health}")
        raise typer.Exit(1)

    # Fetch org info
    try:
        org = c.client.get_org()
        sections = [
            (
                "Health",
                [
                    ("Status", "[green]healthy[/green]"),
                    ("Version", health.get("version", "unknown")),
                    ("Commit", health.get("commit", "unknown")),
                    ("Database", status),
                ],
            ),
            (
                "Organization",
                [
                    ("ID", str(org.get("id", "unknown"))),
                    ("Name", org.get("name", "unknown")),
                ],
            ),
        ]
        out.detail(
            "Grafana Health",
            sections,
            data_for_json={
                "health": health,
                "organization": org,
            },
        )
    except Exception:
        out.warn("Could not fetch org info (check API key permissions)")


@app.command("detailed")
def detailed(ctx: typer.Context) -> None:
    """Detailed health check including all datasources."""
    c: AppContext = ctx.obj
    out = c.output

    # Basic health
    health = c.client.check_health()
    if health.get("database") != "ok":
        out.error(f"Grafana unhealthy: {health}")
        raise typer.Exit(1)

    out.success(f"Grafana API healthy \u2014 v{health.get('version', 'unknown')}")

    # Test all datasources
    out.header("Datasource Health")
    try:
        datasources = c.client.get("/datasources")
        rows: list[list[str]] = []
        all_ok = True
        for ds in datasources:
            ds_uid = ds.get("uid", "")
            ds_name = ds.get("name", "unknown")
            ds_type = ds.get("type", "unknown")
            try:
                result = c.client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                ds_status = result.get("status", "unknown")
                if ds_status == "OK":
                    status_display = "[green]OK[/green]"
                else:
                    status_display = f"[red]{ds_status}[/red]"
                    all_ok = False
            except Exception:
                status_display = "[red]ERROR[/red]"
                all_ok = False

            rows.append([ds_name, ds_type, status_display])

        out.table(
            "Datasource Health",
            [("Name", "cyan"), ("Type", ""), ("Status", "")],
            rows,
        )

        if all_ok:
            out.success("All datasources healthy")
        else:
            out.warn("Some datasources have issues")
    except Exception as e:
        out.error(f"Could not check datasources: {e}")
