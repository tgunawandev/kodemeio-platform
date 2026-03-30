"""Health check commands."""

from __future__ import annotations

import typer

from kctl_gatus.core.callbacks import AppContext
from kctl_gatus.core.resolve import format_duration_ms, status_icon

app = typer.Typer(help="Check Gatus health and endpoint summary.")


@app.command()
def check(ctx: typer.Context) -> None:
    """Check Gatus API health and show an endpoint summary."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Health check
    health_code = client.check_health()
    gatus_ok = health_code == 200

    # Endpoint summary
    try:
        statuses = client.get_endpoint_statuses()
    except Exception:
        statuses = []

    total = len(statuses)
    up = 0
    down = 0
    unknown = 0

    for ep in statuses:
        results = ep.get("results", [])
        if results:
            if results[-1].get("success", False):
                up += 1
            else:
                down += 1
        else:
            unknown += 1

    if out.json_mode:
        out.raw_json(
            {
                "healthy": gatus_ok,
                "health_code": health_code,
                "endpoints": {
                    "total": total,
                    "up": up,
                    "down": down,
                    "unknown": unknown,
                },
            }
        )
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Gatus Health",
            [
                ("API Status", "[green]healthy[/green]" if gatus_ok else f"[red]HTTP {health_code}[/red]"),
                ("URL", client.base_url),
            ],
        ),
        (
            "Endpoints",
            [
                ("Total", str(total)),
                ("Up", f"[green]{up}[/green]"),
                ("Down", f"[red]{down}[/red]" if down > 0 else str(down)),
                ("Unknown", f"[yellow]{unknown}[/yellow]" if unknown > 0 else str(unknown)),
            ],
        ),
    ]

    # Show down endpoints if any
    down_eps = []
    for ep in statuses:
        results = ep.get("results", [])
        if results and not results[-1].get("success", False):
            name = ep.get("name", "unknown")
            group = ep.get("group", "")
            display = f"{group}/{name}" if group else name
            down_eps.append(display)

    if down_eps:
        sections.append(("Down Endpoints", [(ep, "[red]DOWN[/red]") for ep in down_eps]))

    out.detail("Health Check", sections)

    if not gatus_ok:
        raise typer.Exit(1)
    if down > 0:
        raise typer.Exit(2)


@app.command("dashboard")
def dashboard_view(ctx: typer.Context) -> None:
    """Rich table with all endpoints, status, uptime, and response time."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    if not statuses:
        out.warn("No endpoints found")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for ep in statuses:
        name = ep.get("name", "unknown")
        group = ep.get("group", "")
        key = ep.get("key", "")
        results = ep.get("results", [])

        display_name = f"{group}/{name}" if group else name

        if results:
            last = results[-1]
            success = last.get("success", False)
            http_status = str(last.get("httpStatus", "-"))
            duration = format_duration_ms(last.get("duration", 0))
            status = status_icon(success)

            # Calculate success rate from available results
            total_checks = len(results)
            successful_checks = sum(1 for r in results if r.get("success", False))
            success_rate = f"{(successful_checks / total_checks * 100):.1f}%" if total_checks > 0 else "-"

            # Average response time
            durations = [r.get("duration", 0) for r in results if r.get("duration", 0) > 0]
            avg_duration = format_duration_ms(sum(durations) / len(durations)) if durations else "-"
        else:
            status = "[dim]?[/dim]"
            http_status = "-"
            duration = "-"
            success_rate = "-"
            avg_duration = "-"
            success = False

        rows.append([display_name, status, http_status, duration, avg_duration, success_rate])
        json_data.append(
            {
                "name": name,
                "group": group,
                "key": key,
                "success": success,
                "http_status": http_status,
                "last_duration": duration,
                "avg_duration": avg_duration,
                "success_rate": success_rate,
            }
        )

    out.table(
        f"Gatus Dashboard ({len(statuses)} endpoints)",
        [
            ("Endpoint", "cyan"),
            ("Status", ""),
            ("HTTP", ""),
            ("Last", ""),
            ("Avg", ""),
            ("Success Rate", ""),
        ],
        rows,
        data_for_json=json_data,
    )
