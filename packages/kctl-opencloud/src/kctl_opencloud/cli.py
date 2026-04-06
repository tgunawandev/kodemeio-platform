"""Main CLI entry point for kctl-opencloud."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_opencloud import __version__
from kctl_opencloud.commands.config_cmd import app as config_app
from kctl_opencloud.commands.dashboard import app as dashboard_app
from kctl_opencloud.commands.doctor_cmd import app as doctor_app
from kctl_opencloud.commands.groups import app as groups_app
from kctl_opencloud.commands.health import app as health_app
from kctl_opencloud.commands.shares import app as shares_app
from kctl_opencloud.commands.skill_cmd import app as skill_app
from kctl_opencloud.commands.spaces import app as spaces_app
from kctl_opencloud.commands.users import app as users_app
from kctl_opencloud.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-opencloud {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-opencloud",
    help="Kodemeio OpenCloud CLI - manage your OpenCloud file platform.",
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
    token: Annotated[str | None, typer.Option("--token", help="API token override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio OpenCloud CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        token_override=token,
    )


# Register command groups
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(config_app, name="config")
app.add_typer(users_app, name="users")
app.add_typer(groups_app, name="groups")
app.add_typer(spaces_app, name="spaces")
app.add_typer(shares_app, name="shares")
app.add_typer(doctor_app, name="doctor")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-opencloud."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-opencloud", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-opencloud")
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
        path = install_completions("kctl-opencloud", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-opencloud", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
