"""Main CLI entry point for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error

from kctl_supa import __version__
from kctl_supa.commands.config_cmd import app as config_app
from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.exceptions import SupabaseError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-supa {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-supa",
    help="Kodemeio Supabase CLI - manage self-hosted Supabase instances.",
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
    url: Annotated[str | None, typer.Option("--url", help="Supabase URL override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Supabase CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
    )


_P_ADMIN = "Admin & Config"
app.add_typer(config_app, name="config", rich_help_panel=_P_ADMIN)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-supa."""
    actx = ctx.obj
    out = actx.output
    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-supa", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-supa")
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
        path = install_completions("kctl-supa", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-supa", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except SupabaseError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
