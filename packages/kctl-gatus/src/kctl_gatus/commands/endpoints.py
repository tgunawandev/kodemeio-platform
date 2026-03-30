"""Endpoint management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_gatus.core.callbacks import AppContext
from kctl_gatus.core.resolve import format_duration_ms, format_uptime_percent, status_icon

app = typer.Typer(help="Manage and query monitored endpoints.")


@app.command("list")
def list_endpoints(ctx: typer.Context) -> None:
    """List all monitored endpoints with their current status."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    if not statuses:
        out.warn("No endpoints found. Is Gatus running and configured?")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for ep in statuses:
        name = ep.get("name", "unknown")
        group = ep.get("group", "")
        key = ep.get("key", "")
        results = ep.get("results", [])

        if results:
            last = results[-1]
            success = last.get("success", False)
            http_status = str(last.get("httpStatus", "-"))
            duration = format_duration_ms(last.get("duration", 0))
            status = status_icon(success)
        else:
            status = "[dim]?[/dim]"
            http_status = "-"
            duration = "-"
            success = False

        display_name = f"{group}/{name}" if group else name

        rows.append([display_name, key, status, http_status, duration])
        json_data.append(
            {
                "name": name,
                "group": group,
                "key": key,
                "success": success,
                "http_status": http_status,
                "duration": duration,
            }
        )

    out.table(
        f"Endpoints ({len(statuses)})",
        [("Endpoint", "cyan"), ("Key", "dim"), ("Status", ""), ("HTTP", ""), ("Duration", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("get")
def get_endpoint(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Endpoint key (e.g. auto-dokploy_my-service)")],
) -> None:
    """Get detailed status for a specific endpoint."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    ep = client.get_endpoint_status(key)

    if not ep:
        out.error(f"Endpoint not found: {key}")
        raise typer.Exit(1)

    name = ep.get("name", "unknown")
    group = ep.get("group", "")
    results = ep.get("results", [])

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Basic info
    info_kvs: list[tuple[str, str]] = [
        ("Name", name),
        ("Group", group or "(none)"),
        ("Key", key),
    ]

    if results:
        last = results[-1]
        success = last.get("success", False)
        info_kvs.extend(
            [
                ("Status", status_icon(success)),
                ("HTTP Status", str(last.get("httpStatus", "-"))),
                ("Duration", format_duration_ms(last.get("duration", 0))),
                ("Hostname", last.get("hostname", "-")),
                ("Timestamp", str(last.get("timestamp", "-"))),
            ]
        )

        # Show conditions
        conditions = last.get("conditionResults", [])
        if conditions:
            for cond in conditions:
                cond_str = cond.get("condition", "")
                cond_ok = cond.get("success", False)
                icon = "[green]PASS[/green]" if cond_ok else "[red]FAIL[/red]"
                info_kvs.append(("Condition", f"{icon} {cond_str}"))

    sections.append(("Endpoint Details", info_kvs))

    # Recent results summary
    if results:
        total = len(results)
        successful = sum(1 for r in results if r.get("success", False))
        failed = total - successful

        sections.append(
            (
                "Recent Results",
                [
                    ("Total checks", str(total)),
                    ("Successful", f"[green]{successful}[/green]"),
                    ("Failed", f"[red]{failed}[/red]" if failed > 0 else str(failed)),
                ],
            )
        )

    out.detail(f"Endpoint: {name}", sections, data_for_json=ep)


@app.command()
def uptime(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Endpoint key")],
    duration: Annotated[str, typer.Option("--duration", "-d", help="Duration (7d, 30d, 1y)")] = "7d",
) -> None:
    """Get uptime data for an endpoint."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    data = client.get_endpoint_uptimes(key, duration)

    if not data:
        out.error(f"No uptime data for endpoint: {key}")
        raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(data)
        return

    # Gatus returns uptime as a float between 0 and 1
    if isinstance(data, dict):
        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Uptime",
                [
                    ("Key", key),
                    ("Duration", duration),
                ],
            ),
        ]
        # Handle different response formats
        for k, v in data.items():
            if k in ("key", "name", "group"):
                continue
            if isinstance(v, (int, float)):
                sections[0][1].append((k, format_uptime_percent(v) if v <= 1.0 else str(v)))
            else:
                sections[0][1].append((k, str(v)))

        out.detail(f"Uptime: {key} ({duration})", sections)
    else:
        out.text(str(data))


@app.command("response-time")
def response_time(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Endpoint key")],
    duration: Annotated[str, typer.Option("--duration", "-d", help="Duration (7d, 30d, 1y)")] = "7d",
) -> None:
    """Get response time data for an endpoint."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    data = client.get_endpoint_response_times(key, duration)

    if not data:
        out.error(f"No response time data for endpoint: {key}")
        raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(data)
        return

    if isinstance(data, dict):
        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Response Times",
                [
                    ("Key", key),
                    ("Duration", duration),
                ],
            ),
        ]
        for k, v in data.items():
            if k in ("key", "name", "group"):
                continue
            if isinstance(v, (int, float)):
                sections[0][1].append((k, format_duration_ms(v)))
            else:
                sections[0][1].append((k, str(v)))

        out.detail(f"Response Times: {key} ({duration})", sections)
    else:
        out.text(str(data))


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query (matches name or group)")],
) -> None:
    """Search endpoints by name or group."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()
    query_lower = query.lower()

    matches = [
        ep
        for ep in statuses
        if query_lower in ep.get("name", "").lower()
        or query_lower in ep.get("group", "").lower()
        or query_lower in ep.get("key", "").lower()
    ]

    if not matches:
        out.warn(f"No endpoints matching: {query}")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for ep in matches:
        name = ep.get("name", "unknown")
        group = ep.get("group", "")
        key = ep.get("key", "")
        results = ep.get("results", [])

        if results:
            last = results[-1]
            success = last.get("success", False)
            status = status_icon(success)
        else:
            status = "[dim]?[/dim]"
            success = False

        display_name = f"{group}/{name}" if group else name
        rows.append([display_name, key, status])
        json_data.append(
            {
                "name": name,
                "group": group,
                "key": key,
                "success": success,
            }
        )

    out.table(
        f"Search Results for '{query}' ({len(matches)} found)",
        [("Endpoint", "cyan"), ("Key", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )
