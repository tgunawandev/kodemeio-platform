"""Short alias commands for kctl-api.

Hidden commands that delegate to longer command paths.
"""

from __future__ import annotations

import subprocess

import typer

from kctl_api.core.callbacks import AppContext


def register_aliases(app: typer.Typer) -> None:
    """Register hidden short-alias commands on the main app."""

    def _base_cmd(ctx: typer.Context) -> list[str]:
        cmd = ["kctl-api"]
        actx: AppContext = ctx.obj
        if actx.profile:
            cmd.extend(["-p", actx.profile])
        if actx.json_mode:
            cmd.append("--json")
        if actx.quiet:
            cmd.append("-q")
        if actx.format != "pretty" and not actx.json_mode:
            cmd.extend(["-f", actx.format])
        if actx.no_header:
            cmd.append("--no-header")
        if actx.url_override:
            cmd.extend(["--url", actx.url_override])
        if actx.ai_url_override:
            cmd.extend(["--ai-url", actx.ai_url_override])
        if actx.api_key_override:
            cmd.extend(["--api-key", actx.api_key_override])
        if actx.database_url_override:
            cmd.extend(["--database-url", actx.database_url_override])
        if actx.redis_url_override:
            cmd.extend(["--redis-url", actx.redis_url_override])
        return cmd

    @app.command("hc", hidden=True, help="Alias: health all")
    def hc(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "health", "all"])

    @app.command("dl", hidden=True, help="Alias: deploy logs <app>")
    def dl(
        ctx: typer.Context,
        app_name: str = typer.Argument("api-main", help="App name."),
    ) -> None:
        subprocess.run([*_base_cmd(ctx), "deploy", "logs", app_name])

    @app.command("ds", hidden=True, help="Alias: deploy status")
    def ds(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "deploy", "status"])

    @app.command("ul", hidden=True, help="Alias: users list")
    def ul(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "users", "list"])

    @app.command("fl", hidden=True, help="Alias: files list")
    def fl(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "files", "list"])

    @app.command("jo", hidden=True, help="Alias: jobs overview")
    def jo(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "jobs", "overview"])

    @app.command("du", hidden=True, help="Alias: dev up")
    def du(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "dev", "up"])

    @app.command("dd", hidden=True, help="Alias: dev down")
    def dd(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "dev", "down"])

    @app.command("dr", hidden=True, help="Alias: dev rebuild")
    def dr(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "dev", "rebuild"])

    @app.command("tr", hidden=True, help="Alias: test run all")
    def tr(ctx: typer.Context) -> None:
        subprocess.run([*_base_cmd(ctx), "test", "run", "all"])
