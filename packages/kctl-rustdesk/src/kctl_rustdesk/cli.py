"""kctl-rustdesk CLI entry point."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_lib import handle_cli_error
from kctl_lib.exceptions import KctlError

from kctl_rustdesk import __version__
from kctl_rustdesk.commands.audit import app as audit_app
from kctl_rustdesk.commands.backup import app as backup_app
from kctl_rustdesk.commands.config_cmd import app as config_app
from kctl_rustdesk.commands.dashboard import app as dashboard_app
from kctl_rustdesk.commands.health import app as health_app
from kctl_rustdesk.commands.maintenance import app as maintenance_app
from kctl_rustdesk.commands.peers import app as peers_app
from kctl_rustdesk.commands.setup import app as setup_app
from kctl_rustdesk.commands.users import app as users_app
from kctl_rustdesk.core.plugins import discover_and_load_plugins


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


app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(peers_app, name="peers")
app.add_typer(users_app, name="users")
app.add_typer(audit_app, name="audit")
app.add_typer(backup_app, name="backup")
app.add_typer(setup_app, name="setup")
app.add_typer(maintenance_app, name="maintenance")

discover_and_load_plugins(app)


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
