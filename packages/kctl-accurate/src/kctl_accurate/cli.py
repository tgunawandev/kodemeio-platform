"""Main CLI entry point for kctl-accurate."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_accurate import __version__
from kctl_accurate.commands.auth import app as auth_app
from kctl_accurate.commands.config_cmd import app as config_app
from kctl_accurate.core.callbacks import AppContext


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

app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    api_token: Annotated[str | None, typer.Option("--api-token", help="Override Accurate API token")] = None,
    signature_secret: Annotated[
        str | None,
        typer.Option("--signature-secret", help="Override HMAC-SHA256 secret"),
    ] = None,
    db_id: Annotated[int | None, typer.Option("--db-id", help="Override Accurate company db_id")] = None,
    host: Annotated[str | None, typer.Option("--host", help="Override Accurate host")] = None,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version"),
    ] = False,
) -> None:
    """Kodemeio Accurate Online CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        api_token_override=api_token,
        signature_secret_override=signature_secret,
        db_id_override=db_id,
        host_override=host,
    )


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
