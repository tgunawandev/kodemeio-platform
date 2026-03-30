"""Results and history commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_gatus.core.callbacks import AppContext
from kctl_gatus.core.resolve import format_duration_ms, status_icon

app = typer.Typer(help="View endpoint check results and history.")


@app.command("list")
def list_results(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Endpoint key")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results to show")] = 20,
) -> None:
    """Show recent check results for an endpoint."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    ep = client.get_endpoint_status(key)

    if not ep:
        out.error(f"Endpoint not found: {key}")
        raise typer.Exit(1)

    name = ep.get("name", key)
    results = ep.get("results", [])

    if not results:
        out.warn(f"No results for endpoint: {key}")
        return

    # Show most recent first, limited
    recent = list(reversed(results[-limit:]))

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for r in recent:
        success = r.get("success", False)
        http_status = str(r.get("httpStatus", "-"))
        duration = format_duration_ms(r.get("duration", 0))
        timestamp = str(r.get("timestamp", "-"))
        hostname = r.get("hostname", "-")
        status = status_icon(success)

        # Truncate timestamp for display
        ts_display = timestamp[:19] if len(timestamp) > 19 else timestamp

        rows.append([ts_display, status, http_status, duration, hostname])
        json_data.append(
            {
                "timestamp": timestamp,
                "success": success,
                "http_status": http_status,
                "duration_ms": r.get("duration", 0),
                "hostname": hostname,
            }
        )

    out.table(
        f"Results: {name} (last {len(recent)})",
        [("Timestamp", "dim"), ("Status", ""), ("HTTP", ""), ("Duration", ""), ("Hostname", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def summary(ctx: typer.Context) -> None:
    """Show summary of all endpoints: counts of up/down/unknown."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    if not statuses:
        out.warn("No endpoints found")
        return

    total = len(statuses)
    up = 0
    down = 0
    unknown = 0

    groups: dict[str, dict[str, int]] = {}

    for ep in statuses:
        group = ep.get("group", "(ungrouped)")
        results = ep.get("results", [])

        if group not in groups:
            groups[group] = {"up": 0, "down": 0, "unknown": 0, "total": 0}
        groups[group]["total"] += 1

        if results:
            last = results[-1]
            if last.get("success", False):
                up += 1
                groups[group]["up"] += 1
            else:
                down += 1
                groups[group]["down"] += 1
        else:
            unknown += 1
            groups[group]["unknown"] += 1

    if out.json_mode:
        out.raw_json(
            {
                "total": total,
                "up": up,
                "down": down,
                "unknown": unknown,
                "groups": groups,
            }
        )
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Overall",
            [
                ("Total Endpoints", str(total)),
                ("Up", f"[green]{up}[/green]"),
                ("Down", f"[red]{down}[/red]" if down > 0 else str(down)),
                ("Unknown", f"[yellow]{unknown}[/yellow]" if unknown > 0 else str(unknown)),
            ],
        ),
    ]

    for gname, counts in sorted(groups.items()):
        gdown = counts["down"]
        gunk = counts["unknown"]
        kvs: list[tuple[str, str]] = [
            ("Total", str(counts["total"])),
            ("Up", f"[green]{counts['up']}[/green]"),
            ("Down", f"[red]{gdown}[/red]" if gdown > 0 else str(gdown)),
            ("Unknown", f"[yellow]{gunk}[/yellow]" if gunk > 0 else str(gunk)),
        ]
        sections.append((f"Group: {gname}", kvs))

    out.detail("Endpoint Summary", sections)
