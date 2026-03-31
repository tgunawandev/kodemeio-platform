"""Short command aliases for common workflows.

These provide quick shortcuts for frequently used multi-word commands:
    zl  -> zones list
    zg  -> zones get
    rl  -> records list
    hc  -> health check
    cs  -> cache status
    cp  -> cache purge-all
    ss  -> ssl status
    wl  -> workers list
    ea  -> export all
"""

from __future__ import annotations

import subprocess
import sys

import typer

from kctl_cloudflare.core.callbacks import AppContext


def register_aliases(app: typer.Typer) -> None:
    """Register short aliases as hidden top-level commands."""

    def _get_base_cmd(ctx: typer.Context) -> list[str]:
        """Build base command with inherited global options."""
        cmd = ["kctl-cloudflare"]
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

    @app.command("zl", hidden=True, help="Alias: zones list")
    def zl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "zones", "list"]))  # noqa: S603, S607

    @app.command("zg", hidden=True, help="Alias: zones get <zone>")
    def zg(ctx: typer.Context, zone: str) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "zones", "get", zone]))  # noqa: S603, S607

    @app.command("rl", hidden=True, help="Alias: records list")
    def rl(ctx: typer.Context, zone: str = "", type: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "records", "list"]
        if zone:
            cmd.extend(["--zone", zone])
        if type:
            cmd.extend(["--type", type])
        sys.exit(subprocess.call(cmd))  # noqa: S603

    @app.command("hc", hidden=True, help="Alias: health check")
    def hc(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "health", "check"]))  # noqa: S603, S607

    @app.command("cs", hidden=True, help="Alias: cache status")
    def cs(ctx: typer.Context, zone: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "cache", "status"]
        if zone:
            cmd.extend(["--zone", zone])
        sys.exit(subprocess.call(cmd))  # noqa: S603

    @app.command("cp", hidden=True, help="Alias: cache purge-all")
    def cp(ctx: typer.Context, zone: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "cache", "purge-all", "--yes"]
        if zone:
            cmd.extend(["--zone", zone])
        sys.exit(subprocess.call(cmd))  # noqa: S603

    @app.command("ss", hidden=True, help="Alias: ssl status")
    def ss(ctx: typer.Context, zone: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "ssl", "status"]
        if zone:
            cmd.extend(["--zone", zone])
        sys.exit(subprocess.call(cmd))  # noqa: S603

    @app.command("wl", hidden=True, help="Alias: workers list")
    def wl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "workers", "list"]))  # noqa: S603, S607

    @app.command("ea", hidden=True, help="Alias: export all")
    def ea(ctx: typer.Context, zone: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "export", "all"]
        if zone:
            cmd.extend(["--zone", zone])
        sys.exit(subprocess.call(cmd))  # noqa: S603

    @app.command("tl", hidden=True, help="Alias: tunnels list")
    def tl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "tunnels", "list"]))  # noqa: S603, S607

    @app.command("st", hidden=True, help="Alias: status overview")
    def st(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "status", "overview"]))  # noqa: S603, S607

    @app.command("bk", hidden=True, help="Alias: export backup")
    def bk(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "export", "backup"]))  # noqa: S603, S607
