"""Main CLI entry point for kctl-zulip."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_zulip import __version__
from kctl_zulip.commands.alert_words import app as alert_words_app
from kctl_zulip.commands.announce import app as announce_app
from kctl_zulip.commands.config_cmd import app as config_app
from kctl_zulip.commands.dashboard import app as dashboard_app
from kctl_zulip.commands.doctor_cmd import app as doctor_app
from kctl_zulip.commands.drafts import app as drafts_app
from kctl_zulip.commands.emoji import app as emoji_app
from kctl_zulip.commands.groups import app as groups_app
from kctl_zulip.commands.health import app as health_app
from kctl_zulip.commands.invitations import app as invitations_app
from kctl_zulip.commands.linkifiers import app as linkifiers_app
from kctl_zulip.commands.messages import app as messages_app
from kctl_zulip.commands.muted import app as muted_app
from kctl_zulip.commands.presence import app as presence_app
from kctl_zulip.commands.profile_fields import app as profile_fields_app
from kctl_zulip.commands.reactions import app as reactions_app
from kctl_zulip.commands.realm import app as realm_app
from kctl_zulip.commands.scheduled import app as scheduled_app
from kctl_zulip.commands.skill_cmd import app as skill_app
from kctl_zulip.commands.streams import app as streams_app
from kctl_zulip.commands.topics import app as topics_app
from kctl_zulip.commands.users import app as users_app
from kctl_zulip.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-zulip {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-zulip",
    help="Kodemeio Zulip CLI - manage your Zulip team chat.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (shortcut for --format json)")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit headers in CSV output")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Auth email override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Zulip CLI."""
    effective_format = "json" if json_output else output_format

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        profile=profile,
        url_override=url,
        email_override=email,
        api_key_override=api_key,
    )


# Admin & Config
app.add_typer(config_app, name="config", rich_help_panel="Admin & Config")
app.add_typer(users_app, name="users", rich_help_panel="Admin & Config")
app.add_typer(groups_app, name="groups", rich_help_panel="Admin & Config")
app.add_typer(realm_app, name="realm", rich_help_panel="Admin & Config")
app.add_typer(invitations_app, name="invitations", rich_help_panel="Admin & Config")

# Messaging
app.add_typer(messages_app, name="messages", rich_help_panel="Messaging")
app.add_typer(streams_app, name="streams", rich_help_panel="Messaging")
app.add_typer(topics_app, name="topics", rich_help_panel="Messaging")
app.add_typer(announce_app, name="announce", rich_help_panel="Messaging")
app.add_typer(drafts_app, name="drafts", rich_help_panel="Messaging")
app.add_typer(scheduled_app, name="scheduled", rich_help_panel="Messaging")

# Personalization
app.add_typer(emoji_app, name="emoji", rich_help_panel="Personalization")
app.add_typer(reactions_app, name="reactions", rich_help_panel="Personalization")
app.add_typer(presence_app, name="presence", rich_help_panel="Personalization")
app.add_typer(muted_app, name="muted", rich_help_panel="Personalization")
app.add_typer(alert_words_app, name="alert-words", rich_help_panel="Personalization")
app.add_typer(profile_fields_app, name="profile-fields", rich_help_panel="Personalization")
app.add_typer(linkifiers_app, name="linkifiers", rich_help_panel="Personalization")

# Monitoring
app.add_typer(health_app, name="health", rich_help_panel="Monitoring")
app.add_typer(dashboard_app, name="dashboard", rich_help_panel="Monitoring")

# Tools
app.add_typer(doctor_app, name="doctor", rich_help_panel="Tools")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update", rich_help_panel="Tools")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-zulip."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-zulip", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-zulip")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command(rich_help_panel="Tools")
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-zulip", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-zulip", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
