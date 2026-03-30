"""Statistics commands — event volume and error rate trends."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Event and error statistics.")


@app.command("events")
def events(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    period: Annotated[str, typer.Option("--period", help="Time period: 1h, 24h, 7d, 30d")] = "24h",
) -> None:
    """Show event volume for a project or organization."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Map period to stat parameter
        stat_map = {
            "1h": "1h",
            "24h": "24h",
            "7d": "",
            "30d": "",
        }
        stat = stat_map.get(period, "24h")

        if project:
            proj = c.client.resolve_project(project)
            # Use project stats endpoint
            stats_data = c.client.project_get(
                proj,
                "/stats/",
                params={"stat": "received", "resolution": stat or "1d"},
            )
        else:
            # Use org stats endpoint
            stats_data = c.client.org_get(
                "/stats_v2/",
                params={
                    "field": "sum(quantity)",
                    "statsPeriod": period,
                    "category": "error",
                },
            )

        if isinstance(stats_data, list):
            # Time-series data: [[timestamp, count], ...]
            total = sum(point[1] for point in stats_data if isinstance(point, (list, tuple)) and len(point) >= 2)
            rows: list[list[str]] = []
            for point in stats_data[-10:]:  # Last 10 data points
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    rows.append([str(point[0]), str(point[1])])

            out.table(
                f"Event Volume — {project or 'all projects'} ({period})",
                [("Timestamp", "dim"), ("Events", "cyan")],
                rows,
                data_for_json={"total": total, "data": stats_data},
            )
            out.kv("Total events", str(total))
        elif isinstance(stats_data, dict):
            out.detail(
                f"Event Stats — {project or 'all projects'} ({period})",
                [("Stats", [(k, str(v)) for k, v in stats_data.items()])],
                data_for_json=stats_data,
            )
        else:
            out.info("No stats data available")

    except KctlError as e:
        out.error(f"Failed to fetch stats: {e}")
        raise typer.Exit(1) from e


@app.command("errors")
def errors(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    period: Annotated[str, typer.Option("--period", help="Time period: 24h, 7d, 30d")] = "24h",
) -> None:
    """Show error rate trends for a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        proj = c.client.resolve_project(project) if project else None

        if proj:
            # Fetch unresolved issues sorted by frequency
            issues = c.client.project_get(
                proj,
                "/issues/",
                params={"query": "is:unresolved", "sort": "freq", "limit": 10, "statsPeriod": period},
            )
        else:
            # Org-wide: fetch issues across all projects
            issues = c.client.get(
                f"/organizations/{c.client.organization}/issues/",
                params={"query": "is:unresolved", "sort": "freq", "limit": 10, "statsPeriod": period},
            )

        if not isinstance(issues, list):
            issues = []

        rows: list[list[str]] = []
        for iss in issues:
            short_id = iss.get("shortId", "")
            title = (iss.get("title", "") or "")[:50]
            events_count = str(iss.get("count", 0))
            users_count = str(iss.get("userCount", 0))
            proj_slug = ""
            if isinstance(iss.get("project"), dict):
                proj_slug = iss["project"].get("slug", "")
            rows.append([short_id, proj_slug, title, events_count, users_count])

        out.table(
            f"Top Errors — {project or 'all projects'} ({period})",
            [
                ("ID", "cyan"),
                ("Project", ""),
                ("Title", ""),
                ("Events", "yellow"),
                ("Users", ""),
            ],
            rows,
            data_for_json=issues,
        )
    except KctlError as e:
        out.error(f"Failed to fetch error trends: {e}")
        raise typer.Exit(1) from e
