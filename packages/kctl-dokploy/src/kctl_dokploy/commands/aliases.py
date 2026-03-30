"""Hidden command aliases for power users.

Short aliases that re-invoke the full command with context propagation.
Hidden from --help to keep it clean, but discoverable by power users.
"""

from __future__ import annotations

import subprocess
import sys

import typer

from kctl_dokploy.core.callbacks import AppContext


def _base_cmd(ctx: typer.Context) -> list[str]:
    """Build base command with inherited global options."""
    cmd = ["kctl-dokploy"]
    actx: AppContext = ctx.obj
    if actx.profile:
        cmd.extend(["-p", actx.profile])
    if actx.json_mode:
        cmd.append("--json")
    elif actx.format != "pretty":
        cmd.extend(["--format", actx.format])
    if actx.quiet:
        cmd.append("--quiet")
    if actx.debug:
        cmd.append("--debug")
    return cmd


def register_aliases(app: typer.Typer) -> None:
    """Register all hidden alias commands on the main app."""

    @app.command("cl", hidden=True, help="Alias: compose list")
    def cl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "compose", "list"]))

    @app.command("cs", hidden=True, help="Alias: compose start <id>")
    def cs(ctx: typer.Context, compose_id: str = typer.Argument(help="Compose ID")) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "compose", "start", compose_id]))

    @app.command("cr", hidden=True, help="Alias: compose redeploy <id>")
    def cr(ctx: typer.Context, compose_id: str = typer.Argument(help="Compose ID")) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "compose", "redeploy", compose_id]))

    @app.command("sl", hidden=True, help="Alias: servers list")
    def sl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "servers", "list"]))

    @app.command("pl", hidden=True, help="Alias: projects list")
    def pl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "projects", "list"]))

    @app.command("ds", hidden=True, help="Alias: dashboard show")
    def ds(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "dashboard", "show"]))

    @app.command("dg", hidden=True, help="Alias: diagnose run")
    def dg(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "diagnose", "run"]))

    @app.command("pp", hidden=True, help="Alias: pipeline deploy")
    def pp(
        ctx: typer.Context,
        name: str = typer.Option(..., "--name", "-n"),
        project: str = typer.Option(..., "--project", "-p"),
        file: str = typer.Option(..., "--file", "-f"),
    ) -> None:
        sys.exit(
            subprocess.call(
                [
                    *_base_cmd(ctx),
                    "pipeline",
                    "deploy",
                    "--name",
                    name,
                    "--project",
                    project,
                    "--file",
                    file,
                ]
            )
        )

    @app.command("dl", hidden=True, help="Alias: deployments list")
    def dl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "deployments", "list"]))

    @app.command("bl", hidden=True, help="Alias: backups list")
    def bl(ctx: typer.Context) -> None:
        sys.exit(subprocess.call([*_base_cmd(ctx), "backups", "list"]))
