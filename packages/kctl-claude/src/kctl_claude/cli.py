"""Main CLI entry point for kctl-claude."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from kctl_claude import __version__
from kctl_claude.commands.api_cmd import app as api_app
from kctl_claude.commands.backup_cmd import app as backup_app
from kctl_claude.commands.config_cmd import app as config_app
from kctl_claude.commands.doctor_cmd import app as doctor_app
from kctl_claude.commands.env_cmd import app as env_app
from kctl_claude.commands.setup_cmd import app as setup_app
from kctl_claude.commands.status_cmd import app as status_app
from kctl_claude.commands.sync_cmd import app as sync_app
from kctl_claude.commands.verify_cmd import app as verify_app
from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.plugins import ENTRY_POINT_GROUP, discover_and_load_plugins

app = typer.Typer(
    name="kctl-claude",
    help="Kodemeio Claude Code CLI — manage local and remote Claude Code environments.",
    invoke_without_command=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

# Register command groups
app.add_typer(config_app, name="config")
app.add_typer(status_app, name="status")
app.add_typer(sync_app, name="sync")
app.add_typer(verify_app, name="verify")
app.add_typer(api_app, name="api")
app.add_typer(env_app, name="env")
app.add_typer(backup_app, name="backup")
app.add_typer(setup_app, name="setup")
app.add_typer(doctor_app, name="doctor")

# Discover and load plugins
discover_and_load_plugins(app, ENTRY_POINT_GROUP)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show debug output")] = False,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version")] = False,
) -> None:
    """Global options applied to all commands."""
    if version:
        typer.echo(f"kctl-claude {__version__}")
        raise typer.Exit()

    ctx.ensure_object(dict)
    ctx.obj = AppContext(json_mode=json_output, quiet=quiet, verbose=verbose)

    # Record command in history (non-blocking, best-effort)
    try:
        from kctl_common.history import HistoryStore

        store = HistoryStore("kctl-claude")
        store.ensure_schema(
            [
                """CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )"""
            ]
        )
        store.record(table="commands", command=" ".join(sys.argv[1:]))
    except Exception:
        pass  # History recording is best-effort

    # If no subcommand, show help
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_common.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-claude", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-claude", shell)
        typer.echo(script)


@app.command("update")
def update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-claude."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_common.self_update import check_update
    from kctl_common.self_update import update as do_update

    latest = check_update("kctl-claude", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-claude")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
