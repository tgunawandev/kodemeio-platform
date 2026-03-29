"""kctl-rustdesk CLI entry point."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_common import handle_cli_error
from kctl_common.exceptions import KctlError

from kctl_rustdesk import __version__


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-rustdesk {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-rustdesk",
    help="Kodemeio RustDesk CLI — manage RustDesk server infrastructure.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit column headers")] = False,
    host: Annotated[str | None, typer.Option("--host", help="Server host override")] = None,
    version: Annotated[bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)] = False,
) -> None:
    """Manage RustDesk server infrastructure."""
    from kctl_rustdesk.core.callbacks import AppContext

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        host_override=host,
    )


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
