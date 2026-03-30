"""Discovery sidecar management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_gatus.core.callbacks import AppContext

app = typer.Typer(help="Manage the auto-discovery sidecar.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Check if the discovery sidecar is running and show its status."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Check Gatus health first
    health_code = client.check_health()

    # Get endpoint statuses to see if auto-discovered endpoints exist
    try:
        statuses = client.get_endpoint_statuses()
    except Exception:
        statuses = []

    auto_endpoints = [ep for ep in statuses if ep.get("group", "") == "auto-dokploy"]
    core_endpoints = [ep for ep in statuses if ep.get("group", "") != "auto-dokploy"]

    gatus_ok = health_code == 200
    discovery_active = len(auto_endpoints) > 0

    if out.json_mode:
        out.raw_json(
            {
                "gatus_healthy": gatus_ok,
                "discovery_active": discovery_active,
                "auto_discovered_endpoints": len(auto_endpoints),
                "core_endpoints": len(core_endpoints),
                "total_endpoints": len(statuses),
            }
        )
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Discovery Status",
            [
                ("Gatus Health", "[green]healthy[/green]" if gatus_ok else "[red]unhealthy[/red]"),
                (
                    "Discovery Active",
                    "[green]yes[/green]" if discovery_active else "[yellow]no auto-discovered endpoints[/yellow]",
                ),
                ("Auto-Discovered", str(len(auto_endpoints))),
                ("Core Endpoints", str(len(core_endpoints))),
                ("Total Endpoints", str(len(statuses))),
            ],
        ),
    ]

    out.detail("Discovery Sidecar", sections)


@app.command()
def config(ctx: typer.Context) -> None:
    """Show the current discovery configuration (from Gatus endpoint groups)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    # Group endpoints by their group
    groups: dict[str, list[dict]] = {}
    for ep in statuses:
        group = ep.get("group", "(ungrouped)")
        if group not in groups:
            groups[group] = []
        groups[group].append(ep)

    if out.json_mode:
        out.raw_json(
            {group: [{"name": ep.get("name"), "key": ep.get("key")} for ep in eps] for group, eps in groups.items()}
        )
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    for group_name, endpoints in sorted(groups.items()):
        is_auto = group_name == "auto-dokploy"
        label = f"{group_name} [green](auto-discovered)[/green]" if is_auto else group_name

        kvs: list[tuple[str, str]] = [
            ("Endpoints", str(len(endpoints))),
        ]
        for ep in endpoints:
            name = ep.get("name", "unknown")
            key = ep.get("key", "")
            results = ep.get("results", [])
            if results:
                last_success = results[-1].get("success", False)
                status = "[green]UP[/green]" if last_success else "[red]DOWN[/red]"
            else:
                status = "[dim]?[/dim]"
            kvs.append((name, f"{status} [dim]({key})[/dim]"))

        sections.append((label, kvs))

    out.detail("Endpoint Groups", sections)


@app.command()
def trigger(
    ctx: typer.Context,
    container: Annotated[
        str,
        typer.Option("--container", "-c", help="Discovery container name"),
    ] = "gatus-gatus-init-1",
    compose_file: Annotated[
        str,
        typer.Option("--compose-file", "-f", help="Docker Compose file path"),
    ] = "docker-compose.prod.yml",
) -> None:
    """Force a re-discovery run by restarting the discovery sidecar.

    This executes: docker compose -f <file> restart gatus-init
    """
    actx: AppContext = ctx.obj
    out = actx.output

    import subprocess

    out.info("Triggering discovery run by restarting gatus-init...")

    try:
        result = subprocess.run(
            ["docker", "compose", "-f", compose_file, "restart", "gatus-init"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            out.success("Discovery sidecar restarted — will re-discover endpoints")
            if result.stdout.strip():
                out.text(result.stdout.strip())
        else:
            out.error(f"Failed to restart discovery sidecar: {result.stderr.strip()}")
            out.info("Make sure you are in the project directory or use --compose-file")
            raise typer.Exit(1)
    except FileNotFoundError:
        out.error("docker compose not found. Is Docker installed?")
        raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        out.error("Restart timed out after 30 seconds")
        raise typer.Exit(1)

    if out.json_mode:
        out.raw_json({"action": "restart", "service": "gatus-init", "success": True})


@app.command("endpoints")
def discovered_endpoints(ctx: typer.Context) -> None:
    """List only auto-discovered endpoints (group: auto-dokploy)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    auto_endpoints = [ep for ep in statuses if ep.get("group", "") == "auto-dokploy"]

    if not auto_endpoints:
        out.warn("No auto-discovered endpoints found")
        out.info("The discovery sidecar may not have run yet, or no domains were found")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for ep in auto_endpoints:
        name = ep.get("name", "unknown")
        key = ep.get("key", "")
        results = ep.get("results", [])

        if results:
            last = results[-1]
            success = last.get("success", False)
            http_status = str(last.get("httpStatus", "-"))
            status = "[green]UP[/green]" if success else "[red]DOWN[/red]"
        else:
            status = "[dim]?[/dim]"
            http_status = "-"
            success = False

        rows.append([name, key, status, http_status])
        json_data.append(
            {
                "name": name,
                "key": key,
                "success": success,
                "http_status": http_status,
            }
        )

    out.table(
        f"Auto-Discovered Endpoints ({len(auto_endpoints)})",
        [("Name", "cyan"), ("Key", "dim"), ("Status", ""), ("HTTP", "")],
        rows,
        data_for_json=json_data,
    )
