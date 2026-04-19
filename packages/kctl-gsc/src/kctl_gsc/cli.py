"""Main CLI entry point for kctl-gsc."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_gsc import __version__
from kctl_gsc.commands.config_cmd import app as config_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-gsc {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-gsc",
    help="Kodemeio Google Search Console CLI — properties, queries, indexing, reports.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

app.add_typer(config_app, name="config", rich_help_panel="Admin")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    output_format: Annotated[str, typer.Option("--format", "-f")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p")] = None,
    property_override: Annotated[str | None, typer.Option("--property")] = None,
    credentials_file: Annotated[str | None, typer.Option("--credentials-file")] = None,
    version: Annotated[bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)] = False,
) -> None:
    """Kodemeio Google Search Console CLI."""
    from kctl_gsc.core.callbacks import AppContext

    effective_format = "json" if json_output else output_format
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        profile=profile,
        property_override=property_override,
        credentials_file_override=credentials_file,
    )


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
