"""Port mapping management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage port mappings for applications.")


@app.command()
def get(
    ctx: typer.Context,
    port_id: Annotated[str, typer.Argument(help="Port mapping ID")],
) -> None:
    """Get port mapping details."""
    c: AppContext = ctx.obj
    data = c.client.get("/port.one", params={"portId": port_id})
    if not isinstance(data, dict):
        c.output.error(f"Port mapping '{port_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Port Mapping",
            [
                ("ID", data.get("portId", "")),
                ("Published Port", str(data.get("publishedPort", ""))),
                ("Target Port", str(data.get("targetPort", ""))),
                ("Protocol", data.get("protocol", "")),
                ("Publish Mode", data.get("publishMode", "")),
                ("Application ID", data.get("applicationId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Port Mapping: {data.get('portId', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Option("--application", "-a", help="Application ID")],
    published: Annotated[int, typer.Option("--published", "-p", help="Published (host) port")],
    target: Annotated[int, typer.Option("--target", "-t", help="Target (container) port")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol (tcp or udp)")] = "tcp",
    mode: Annotated[str, typer.Option("--mode", "-m", help="Publish mode (ingress or host)")] = "ingress",
) -> None:
    """Create a new port mapping."""
    c: AppContext = ctx.obj
    payload: dict = {
        "applicationId": application_id,
        "publishedPort": published,
        "targetPort": target,
        "protocol": protocol,
        "publishMode": mode,
    }
    result = c.client.post("/port.create", json=payload)
    pid = result.get("portId", "") if isinstance(result, dict) else ""
    c.output.success(f"Port mapping created: {pid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    port_id: Annotated[str, typer.Argument(help="Port mapping ID")],
    published: Annotated[int | None, typer.Option("--published", "-p", help="New published port")] = None,
    target: Annotated[int | None, typer.Option("--target", "-t", help="New target port")] = None,
    protocol: Annotated[str | None, typer.Option("--protocol", help="New protocol (tcp or udp)")] = None,
    mode: Annotated[str | None, typer.Option("--mode", "-m", help="New publish mode")] = None,
) -> None:
    """Update a port mapping."""
    c: AppContext = ctx.obj
    payload: dict = {"portId": port_id}
    if published is not None:
        payload["publishedPort"] = published
    if target is not None:
        payload["targetPort"] = target
    if protocol is not None:
        payload["protocol"] = protocol
    if mode is not None:
        payload["publishMode"] = mode
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/port.update", json=payload)
    c.output.success(f"Port mapping '{port_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    port_id: Annotated[str, typer.Argument(help="Port mapping ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a port mapping (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete port mapping '{port_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/port.delete", json={"portId": port_id})
    c.output.success(f"Port mapping '{port_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)
