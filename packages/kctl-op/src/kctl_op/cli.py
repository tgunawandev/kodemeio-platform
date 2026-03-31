"""Main Typer application for kctl-op."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from kctl_op import __version__
from kctl_op.commands.backup import app as backup_app

# Command group imports
from kctl_op.commands.config_cmd import app as config_app
from kctl_op.commands.diff_cmd import app as diff_app
from kctl_op.commands.discover import app as discover_app
from kctl_op.commands.health import app as health_app
from kctl_op.commands.projects import app as projects_app
from kctl_op.commands.status import app as status_app
from kctl_op.commands.sync_cmd import pull_app, push_app
from kctl_op.commands.vault import app as vault_app
from kctl_op.core.callbacks import AppContext
from kctl_lib import handle_cli_error
from kctl_op.core.exceptions import (
    KctlError,
)


def _version_callback(value: bool) -> None:
    if value:
        print(f"kctl-op {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-op",
    help="Kodemeio 1Password CLI - manage secrets across all projects via 1Password.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output in JSON format.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress non-essential output.")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile to use.")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml.")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit header row in CSV output.")] = False,
    vault: Annotated[str | None, typer.Option("--vault", help="Override vault name.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="Override service account token.")] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Global options applied to all commands."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        vault_override=vault,
        token_override=token,
    )


# Register command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(discover_app, name="discover")
app.add_typer(status_app, name="status")
app.add_typer(push_app, name="push")
app.add_typer(pull_app, name="pull")
app.add_typer(diff_app, name="diff")
app.add_typer(vault_app, name="vault")
app.add_typer(projects_app, name="projects")
app.add_typer(backup_app, name="backup")


# Top-level convenience commands
@app.command(name="list")
def list_items(ctx: typer.Context) -> None:
    """List all items in the 1Password vault."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    try:
        items = client.list_items()
    except Exception as e:
        out.error(f"Cannot list items: {e}")
        raise typer.Exit(code=1) from e

    if not items:
        out.info("No items in vault.")
        return

    rows = []
    json_data = []
    for item in items:
        title = item.get("title", "untitled")
        tags = ", ".join(item.get("tags", []))
        updated = item.get("updated_at", "unknown")
        rows.append([title, tags, updated])
        json_data.append(
            {
                "title": title,
                "id": item.get("id", ""),
                "tags": item.get("tags", []),
                "updated_at": updated,
            }
        )

    out.table(
        title=f"Vault Items ({len(items)})",
        columns=[
            ("Title", "green"),
            ("Tags", "cyan"),
            ("Updated", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    _run()
