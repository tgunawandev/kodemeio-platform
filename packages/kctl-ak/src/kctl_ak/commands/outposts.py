"""Outpost management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Outpost instance and service connection management.")

SERVICE_CONNECTION_ENDPOINTS = {
    "docker": "outposts/service_connections/docker/",
    "kubernetes": "outposts/service_connections/kubernetes/",
}


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all outpost instances."""
    c: AppContext = ctx.obj
    data = c.client.get_all("outposts/instances/")

    rows = []
    for o in data:
        providers_list = o.get("providers", [])
        service_connection = o.get("service_connection_obj", {})
        conn_name = ""
        if isinstance(service_connection, dict) and service_connection:
            conn_name = service_connection.get("name", "")
        rows.append(
            [
                str(o.get("pk", ""))[:8],
                o.get("name", ""),
                o.get("type", ""),
                str(len(providers_list)),
                conn_name or "[dim]embedded[/dim]",
            ]
        )

    c.output.table(
        "Outposts",
        [("ID", "dim"), ("Name", "cyan"), ("Type", "yellow"), ("Providers", ""), ("Connection", "dim")],
        rows,
        data_for_json=data,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Outpost UUID")],
) -> None:
    """Get outpost details."""
    c: AppContext = ctx.obj
    o = c.client.get(f"outposts/instances/{id_}/")

    providers_list = o.get("providers", [])
    providers_obj = o.get("providers_obj", [])
    provider_names = (
        [p.get("name", str(p.get("pk", ""))) for p in providers_obj]
        if providers_obj
        else [str(p) for p in providers_list]
    )

    service_connection = o.get("service_connection_obj", {})
    conn_name = ""
    if isinstance(service_connection, dict) and service_connection:
        conn_name = service_connection.get("name", "")

    config = o.get("config", {})
    config_kvs = [(k, str(v)) for k, v in config.items()] if isinstance(config, dict) else []

    sections = [
        (
            "Outpost",
            [
                ("ID", str(o.get("pk", ""))),
                ("Name", o.get("name", "")),
                ("Type", o.get("type", "")),
                ("Service Connection", conn_name or "(embedded)"),
                ("Providers", ", ".join(provider_names) if provider_names else "(none)"),
            ],
        ),
    ]
    if config_kvs:
        sections.append(("Config", config_kvs))

    c.output.detail(o.get("name", str(id_)), sections, data_for_json=o)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Outpost name")],
    type_: Annotated[str, typer.Option("--type", help="Outpost type: proxy, ldap, radius")] = "proxy",
    providers: Annotated[str | None, typer.Option("--providers", help="Comma-separated provider PKs")] = None,
    service_connection: Annotated[
        str | None, typer.Option("--service-connection", help="Service connection UUID")
    ] = None,
) -> None:
    """Create an outpost instance."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "type": type_,
    }
    if providers:
        payload["providers"] = [int(p.strip()) for p in providers.split(",") if p.strip()]
    if service_connection:
        payload["service_connection"] = service_connection

    result = c.client.post("outposts/instances/", data=payload)
    c.output.success(f"Created outpost '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command()
def update(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Outpost UUID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    providers: Annotated[
        str | None, typer.Option("--providers", help="Comma-separated provider PKs (replaces existing)")
    ] = None,
    service_connection: Annotated[
        str | None, typer.Option("--service-connection", help="Service connection UUID")
    ] = None,
) -> None:
    """Update an outpost instance."""
    c: AppContext = ctx.obj

    # Fetch current state to merge
    current = c.client.get(f"outposts/instances/{id_}/")
    payload: dict = {
        "name": current.get("name", ""),
        "type": current.get("type", "proxy"),
        "providers": current.get("providers", []),
    }

    if name is not None:
        payload["name"] = name
    if providers is not None:
        payload["providers"] = [int(p.strip()) for p in providers.split(",") if p.strip()]
    if service_connection is not None:
        payload["service_connection"] = service_connection

    result = c.client.put(f"outposts/instances/{id_}/", data=payload)
    c.output.success(f"Updated outpost '{result.get('name', id_)}'")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Outpost UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an outpost instance."""
    if not force:
        typer.confirm(f"Delete outpost {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"outposts/instances/{id_}/")
    c.output.success(f"Deleted outpost {id_}")


@app.command()
def health(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Outpost UUID")],
) -> None:
    """Check outpost health."""
    c: AppContext = ctx.obj
    data = c.client.get(f"outposts/instances/{id_}/health/")

    if c.output.json_mode:
        c.output.raw_json(data)
        return

    if isinstance(data, list):
        if not data:
            c.output.warn(f"No health data for outpost {id_[:8]}... (outpost may be offline)")
            return
        for entry in data:
            version = entry.get("version", "-")
            version_should = entry.get("version_should", "-")
            version_outdated = entry.get("version_outdated", False)
            last_seen = entry.get("last_seen", "-")
            build_hash = entry.get("build_hash", "-")

            version_display = version
            if version_outdated:
                version_display = f"[yellow]{version}[/yellow] (should be {version_should})"

            sections = [
                (
                    "Health",
                    [
                        ("Version", version_display),
                        ("Expected Version", version_should),
                        ("Outdated", "[yellow]yes[/yellow]" if version_outdated else "[green]no[/green]"),
                        ("Last Seen", str(last_seen)),
                        ("Build Hash", str(build_hash)[:12]),
                    ],
                ),
            ]
            c.output.detail(f"Outpost Health ({id_[:8]}...)", sections)
    else:
        c.output.raw_json(data)


@app.command()
def connections(ctx: typer.Context) -> None:
    """List all service connections."""
    c: AppContext = ctx.obj
    data = c.client.get_all("outposts/service_connections/all/")

    rows = []
    for conn in data:
        rows.append(
            [
                str(conn.get("pk", "")),
                conn.get("verbose_name", conn.get("object_type", "")),
                conn.get("name", ""),
                str(conn.get("local", False)),
            ]
        )

    c.output.table(
        "Service Connections",
        [("ID", "cyan"), ("Type", "yellow"), ("Name", ""), ("Local", "")],
        rows,
        data_for_json=data,
    )


@app.command("create-connection")
def create_connection(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Connection name")],
    type_: Annotated[str, typer.Option("--type", help="Connection type: docker, kubernetes")] = "docker",
    local: Annotated[bool, typer.Option("--local/--url", help="Use local Docker socket or remote URL")] = True,
    url: Annotated[str | None, typer.Option("--connection-url", help="Remote connection URL")] = None,
) -> None:
    """Create a service connection."""
    c: AppContext = ctx.obj
    endpoint = SERVICE_CONNECTION_ENDPOINTS.get(type_)
    if not endpoint:
        c.output.error(f"Unknown connection type: {type_}. Valid: {', '.join(SERVICE_CONNECTION_ENDPOINTS)}")
        raise typer.Exit(1)

    payload: dict = {
        "name": name,
        "local": local,
    }
    if url:
        payload["url"] = url

    result = c.client.post(endpoint, data=payload)
    c.output.success(f"Created {type_} service connection '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@app.command("delete-connection")
def delete_connection(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Service connection UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a service connection."""
    if not force:
        typer.confirm(f"Delete service connection {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"outposts/service_connections/all/{id_}/")
    c.output.success(f"Deleted service connection {id_}")
