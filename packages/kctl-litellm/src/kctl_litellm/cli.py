"""Main CLI entry point for kctl-litellm."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error

from kctl_litellm import __version__
from kctl_litellm.commands.budgets_cmd import app as budgets_app
from kctl_litellm.commands.config_cmd import app as config_app
from kctl_litellm.commands.health_cmd import app as health_app
from kctl_litellm.commands.keys_cmd import app as keys_app
from kctl_litellm.commands.logs_cmd import app as logs_app
from kctl_litellm.commands.models_cmd import app as models_app
from kctl_litellm.commands.spend_cmd import app as spend_app
from kctl_litellm.commands.teams_cmd import app as teams_app
from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.exceptions import LiteLLMError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-litellm {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-litellm",
    help="Kodemeio LiteLLM CLI - manage LiteLLM proxy instances.",
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
    url: Annotated[str | None, typer.Option("--url", help="LiteLLM URL override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio LiteLLM CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
    )


_P_ADMIN = "Admin & Config"
app.add_typer(config_app, name="config", rich_help_panel=_P_ADMIN)

_P_SERVICES = "Services"
app.add_typer(health_app, name="health", rich_help_panel=_P_SERVICES)
app.add_typer(models_app, name="models", rich_help_panel=_P_SERVICES)

_P_KEYS = "Key Management"
app.add_typer(keys_app, name="keys", rich_help_panel=_P_KEYS)

_P_TEAMS = "Teams & Budgets"
app.add_typer(teams_app, name="teams", rich_help_panel=_P_TEAMS)
app.add_typer(budgets_app, name="budgets", rich_help_panel=_P_TEAMS)

_P_USAGE = "Usage & Spend"
app.add_typer(spend_app, name="spend", rich_help_panel=_P_USAGE)
app.add_typer(logs_app, name="logs", rich_help_panel=_P_USAGE)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-litellm."""
    actx = ctx.obj
    out = actx.output
    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-litellm", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-litellm")
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
        path = install_completions("kctl-litellm", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-litellm", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except LiteLLMError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
