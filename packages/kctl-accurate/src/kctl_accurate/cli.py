"""Main CLI entry point for kctl-accurate."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_accurate import __version__


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-accurate {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-accurate",
    help="Kodemeio Accurate Online CLI — general-purpose ops on the Accurate API.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version"),
    ] = False,
) -> None:
    """Kodemeio Accurate Online CLI."""
    ctx.ensure_object(dict)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
