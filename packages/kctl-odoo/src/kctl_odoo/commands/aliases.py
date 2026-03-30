"""Short command aliases for common workflows.

These provide quick shortcuts for frequently used multi-word commands:
    mi  -> modules install
    mu  -> modules upgrade
    ml  -> modules list
    hc  -> troubleshoot check
    di  -> dashboard info
    bl  -> bundles list
    bi  -> bundles install
    pl  -> profiles list
    pi  -> profiles install
    tr  -> test run
"""

from __future__ import annotations

import subprocess
import sys

import typer

from kctl_odoo.core.callbacks import AppContext


def register_aliases(app: typer.Typer) -> None:
    """Register short aliases as hidden top-level commands."""

    def _get_base_cmd(ctx: typer.Context) -> list[str]:
        """Build base command with inherited global options."""
        cmd = ["kctl-odoo"]
        actx: AppContext = ctx.obj
        if actx.profile:
            cmd.extend(["-p", actx.profile])
        if actx.json_mode:
            cmd.append("--json")
        if actx.quiet:
            cmd.append("-q")
        if actx.url_override:
            cmd.extend(["--url", actx.url_override])
        if actx.database_override:
            cmd.extend(["-d", actx.database_override])
        if actx.format and actx.format != "pretty":
            cmd.extend(["--format", actx.format])
        if actx.no_header:
            cmd.append("--no-header")
        return cmd

    @app.command("mi", hidden=True, help="Alias: modules install <names>")
    def mi(ctx: typer.Context, names: str) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "modules", "install", names]))

    @app.command("mu", hidden=True, help="Alias: modules upgrade <names>")
    def mu(ctx: typer.Context, names: str) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "modules", "upgrade", names]))

    @app.command("ml", hidden=True, help="Alias: modules list")
    def ml(ctx: typer.Context, state: str = "installed") -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "modules", "list", "--state", state]))

    @app.command("hc", hidden=True, help="Alias: troubleshoot check")
    def hc(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "troubleshoot", "check"]))

    @app.command("di", hidden=True, help="Alias: dashboard info")
    def di(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "dashboard", "info"]))

    @app.command("bl", hidden=True, help="Alias: bundles list")
    def bl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "bundles", "list"]))

    @app.command("bi", hidden=True, help="Alias: bundles install <name>")
    def bi(ctx: typer.Context, name: str, groups: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "bundles", "install", name]
        if groups:
            cmd.extend(["-g", groups])
        sys.exit(subprocess.call(cmd))

    @app.command("pl", hidden=True, help="Alias: profiles list")
    def pl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "profiles", "list"]))

    @app.command("pi", hidden=True, help="Alias: profiles install <name>")
    def pi(ctx: typer.Context, name: str) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "profiles", "install", name]))

    @app.command("tr", hidden=True, help="Alias: test run <module>")
    def tr(ctx: typer.Context, module: str, tags: str = "") -> None:
        cmd = [*_get_base_cmd(ctx), "test", "run", module]
        if tags:
            cmd.extend(["--tags", tags])
        sys.exit(subprocess.call(cmd))

    @app.command("ms", hidden=True, help="Alias: modules scan")
    def ms(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "modules", "scan"]))

    @app.command("dd", hidden=True, help="Alias: dashboard digest")
    def dd(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_get_base_cmd(ctx), "dashboard", "digest"]))
