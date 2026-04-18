"""Main CLI entry point for kctl-outline."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline import __version__
from kctl_outline.commands.attachments import app as attachments_app
from kctl_outline.commands.collections import app as collections_app
from kctl_outline.commands.comments import app as comments_app
from kctl_outline.commands.config_cmd import app as config_app
from kctl_outline.commands.dashboard import app as dashboard_app
from kctl_outline.commands.doctor_cmd import app as doctor_app
from kctl_outline.commands.documents import app as documents_app
from kctl_outline.commands.events import app as events_app
from kctl_outline.commands.groups import app as groups_app
from kctl_outline.commands.health import app as health_app
from kctl_outline.commands.revisions import app as revisions_app
from kctl_outline.commands.search import search_command
from kctl_outline.commands.shares import app as shares_app
from kctl_outline.commands.stars import app as stars_app
from kctl_outline.commands.sync import app as sync_app
from kctl_outline.commands.templates import app as templates_app
from kctl_outline.commands.tokens import app as tokens_app
from kctl_outline.commands.users import app as users_app
from kctl_outline.core.callbacks import AppContext
from kctl_outline.core.exceptions import APIError, AuthenticationError, ConfigError, KctlError
from kctl_outline.core.exceptions import ConnectionError as KctlConnectionError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-outline {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-outline",
    help="Kodemeio Outline CLI - manage your Outline wiki instances.",
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
    """Kodemeio Outline CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        token_override=token,
    )


# Register all command groups
app.add_typer(documents_app, name="documents")
app.add_typer(collections_app, name="collections")
app.add_typer(users_app, name="users")
app.add_typer(groups_app, name="groups")
app.add_typer(shares_app, name="shares")
app.add_typer(comments_app, name="comments")
app.add_typer(events_app, name="events")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(config_app, name="config")
app.add_typer(doctor_app, name="doctor")
app.add_typer(stars_app, name="stars")
app.add_typer(templates_app, name="templates")
app.add_typer(revisions_app, name="revisions")
app.add_typer(attachments_app, name="attachments")
app.add_typer(tokens_app, name="tokens")
app.add_typer(sync_app, name="sync")

# Top-level search command
app.command("search")(search_command)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlConnectionError as e:
        typer.echo(f"Connection error: {e}", err=True)
        raise typer.Exit(1) from e
    except AuthenticationError as e:
        typer.echo(f"Auth error: {e}", err=True)
        raise typer.Exit(1) from e
    except APIError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1) from e
    except ConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        raise typer.Exit(1) from e
    except KctlError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    _run()
