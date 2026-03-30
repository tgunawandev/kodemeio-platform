"""Short command aliases for common workflows.

These provide quick shortcuts for frequently used multi-word commands:
    sl  -> servers list
    sg  -> servers get <name>
    sc  -> servers create <name>
    hc  -> health check
    ss  -> status show
    vl  -> volumes list
    fl  -> firewalls list
    nl  -> networks list
    ce  -> costs estimate
    dz  -> dns zones
"""

from __future__ import annotations

import subprocess
import sys

import typer

from kctl_hetzner.core.callbacks import AppContext


def register_aliases(app: typer.Typer) -> None:
    """Register short aliases as hidden top-level commands."""

    def _get_base_cmd(ctx: typer.Context) -> list[str]:
        """Build base command with inherited global options."""
        cmd = ["kctl-hetzner"]
        actx: AppContext = ctx.obj
        if actx.profile:
            cmd.extend(["-p", actx.profile])
        if actx.json_mode:
            cmd.append("--json")
        if actx.quiet:
            cmd.append("-q")
        if actx.format and actx.format != "pretty":
            cmd.extend(["--format", actx.format])
        if actx.no_header:
            cmd.append("--no-header")
        return cmd

    @app.command("sl", hidden=True, help="Alias: servers list")
    def sl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "servers", "list"]))

    @app.command("sg", hidden=True, help="Alias: servers get <name>")
    def sg(ctx: typer.Context, name: str) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "servers", "get", name]))

    @app.command("sc", hidden=True, help="Alias: servers create <name>")
    def sc(ctx: typer.Context, name: str, server_type: str = "cx22", image: str = "ubuntu-24.04") -> None:
        sys.exit(
            subprocess.call([*_get_base_cmd(ctx), "servers", "create", name, "--type", server_type, "--image", image])
        )

    @app.command("hc", hidden=True, help="Alias: health check")
    def hc(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "health", "check"]))

    @app.command("ss", hidden=True, help="Alias: status show")
    def ss(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "status", "show"]))

    @app.command("vl", hidden=True, help="Alias: volumes list")
    def vl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "volumes", "list"]))

    @app.command("fl", hidden=True, help="Alias: firewalls list")
    def fl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "firewalls", "list"]))

    @app.command("nl", hidden=True, help="Alias: networks list")
    def nl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "networks", "list"]))

    @app.command("ce", hidden=True, help="Alias: costs estimate")
    def ce(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "costs", "estimate"]))

    @app.command("dz", hidden=True, help="Alias: dns zones")
    def dz(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "dns", "zones"]))
