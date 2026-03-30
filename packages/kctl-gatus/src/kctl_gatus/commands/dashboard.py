"""Dashboard overview commands."""

from __future__ import annotations

import typer

from kctl_gatus.core.callbacks import AppContext
from kctl_gatus.core.resolve import format_duration_ms, status_icon, uptime_color

app = typer.Typer(help="Dashboard overview with comprehensive metrics.")


@app.command()
def overview(ctx: typer.Context) -> None:
    """Show comprehensive dashboard: groups, up/down counts, worst performers."""
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

    groups: dict[str, list[dict]] = {}
    worst_performers: list[dict] = []

    for ep in statuses:
        group = ep.get("group", "(ungrouped)")
        name = ep.get("name", "unknown")
        results = ep.get("results", [])

        if group not in groups:
            groups[group] = []
        groups[group].append(ep)

        if results:
            last = results[-1]
            success = last.get("success", False)
            if success:
                up += 1
            else:
                down += 1

            # Calculate success rate for worst performers
            total_checks = len(results)
            successful_checks = sum(1 for r in results if r.get("success", False))
            success_rate = successful_checks / total_checks if total_checks > 0 else 0.0

            # Average response time
            durations = [r.get("duration", 0) for r in results if r.get("duration", 0) > 0]
            avg_duration = sum(durations) / len(durations) if durations else 0

            worst_performers.append(
                {
                    "name": f"{group}/{name}" if group else name,
                    "success_rate": success_rate,
                    "avg_duration_ms": avg_duration,
                    "last_success": success,
                }
            )
        else:
            unknown += 1

    # Sort worst performers by success rate ascending (worst first)
    worst_performers.sort(key=lambda x: (x["success_rate"], -x["avg_duration_ms"]))

    if out.json_mode:
        out.raw_json(
            {
                "total_endpoints": total,
                "up": up,
                "down": down,
                "unknown": unknown,
                "groups": {g: len(eps) for g, eps in groups.items()},
                "worst_performers": worst_performers[:10],
            }
        )
        return

    # Overall status
    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Overview",
            [
                ("Total Endpoints", str(total)),
                ("Up", f"[green]{up}[/green]"),
                ("Down", f"[red]{down}[/red]" if down > 0 else str(down)),
                ("Unknown", f"[yellow]{unknown}[/yellow]" if unknown > 0 else str(unknown)),
                ("Groups", str(len(groups))),
            ],
        ),
    ]

    # Group breakdown
    group_kvs: list[tuple[str, str]] = []
    for gname, eps in sorted(groups.items()):
        g_total = len(eps)
        g_up = sum(1 for ep in eps if ep.get("results") and ep["results"][-1].get("success", False))
        g_down = g_total - g_up
        is_auto = gname == "auto-dokploy"
        label = f"{gname} [dim](auto)[/dim]" if is_auto else gname
        status = f"[green]{g_up}[/green]/{g_total}"
        if g_down > 0:
            status += f" ([red]{g_down} down[/red])"
        group_kvs.append((label, status))

    sections.append(("Groups", group_kvs))

    # Worst performers (top 10)
    if worst_performers:
        worst_kvs: list[tuple[str, str]] = []
        for wp in worst_performers[:10]:
            rate = wp["success_rate"]
            rate_pct = f"{rate * 100:.1f}%"
            color = uptime_color(rate)
            avg_dur = format_duration_ms(wp["avg_duration_ms"])
            status = status_icon(wp["last_success"])
            worst_kvs.append(
                (
                    wp["name"],
                    f"{status} rate: [{color}]{rate_pct}[/{color}]  avg: {avg_dur}",
                )
            )
        sections.append(("Worst Performers (by success rate)", worst_kvs))

    # Down endpoints
    down_eps = [wp["name"] for wp in worst_performers if not wp["last_success"]]
    if down_eps:
        sections.append(("Currently Down", [(ep, "[red]DOWN[/red]") for ep in down_eps]))

    out.detail("Gatus Dashboard", sections)
