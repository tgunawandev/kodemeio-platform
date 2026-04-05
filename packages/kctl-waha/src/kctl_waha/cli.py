"""Main CLI entry point for kctl-waha."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_waha import __version__
from kctl_waha.commands.bridge import app as bridge_app
from kctl_waha.commands.config_cmd import app as config_app
from kctl_waha.commands.dashboard import app as dashboard_app
from kctl_waha.commands.health import app as health_app
from kctl_waha.commands.messages import app as messages_app
from kctl_waha.commands.sessions import app as sessions_app
from kctl_waha.commands.webhooks import app as webhooks_app
from kctl_waha.core.callbacks import AppContext
from kctl_waha.commands.skill_cmd import app as skill_app
from kctl_waha.commands.doctor_cmd import app as doctor_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-waha {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-waha",
    help="Kodemeio WAHA CLI - manage WhatsApp HTTP API instances.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    bridge_url: Annotated[str | None, typer.Option("--bridge-url", help="Bridge URL override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio WAHA CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
        bridge_url_override=bridge_url,
    )


# Register all command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(sessions_app, name="sessions")
app.add_typer(messages_app, name="messages")
app.add_typer(webhooks_app, name="webhooks")
app.add_typer(bridge_app, name="bridge")
app.add_typer(skill_app, name="skill", hidden=True)
app.add_typer(doctor_app, name="doctor")


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-waha."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-waha", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-waha")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command()
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-waha", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-waha", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
