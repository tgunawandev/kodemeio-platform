"""Infrastructure dashboard command."""

from __future__ import annotations

import typer

from kctl_hetzner.core.callbacks import AppContext

app = typer.Typer(help="Infrastructure dashboard.")


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Show infrastructure dashboard."""
    c: AppContext = ctx.obj
    out = c.output

    servers = c.client.get_all("/servers", "servers")
    volumes = c.client.get_all("/volumes", "volumes")

    sections = [
        (
            "Overview",
            [
                ("Servers", str(len(servers))),
                ("Volumes", str(len(volumes))),
            ],
        ),
    ]
    for s in servers:
        public_net = s.get("public_net", {})
        ipv4 = public_net.get("ipv4", {}).get("ip", "-")
        stype = s.get("server_type", {}).get("name", "")
        sections.append(
            (
                f"Server: {s.get('name', '')}",
                [
                    ("Status", s.get("status", "")),
                    ("Type", stype),
                    ("IP", ipv4),
                    ("DC", s.get("datacenter", {}).get("name", "")),
                ],
            )
        )

    out.detail(
        "Hetzner Dashboard",
        sections,
        data_for_json={
            "servers": len(servers),
            "volumes": len(volumes),
            "server_list": [
                {"name": s.get("name"), "status": s.get("status"), "type": s.get("server_type", {}).get("name")}
                for s in servers
            ],
        },
    )
