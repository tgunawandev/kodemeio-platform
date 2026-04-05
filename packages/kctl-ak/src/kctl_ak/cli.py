"""Main CLI entry point for kctl-ak."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_ak import __version__
from kctl_ak.commands.apps import app as apps_app
from kctl_ak.commands.audit import app as audit_app
from kctl_ak.commands.blueprints import app as blueprints_app
from kctl_ak.commands.brands import app as brands_app
from kctl_ak.commands.certificates import app as certificates_app
from kctl_ak.commands.config_cmd import app as config_app
from kctl_ak.commands.dashboard import app as dashboard_app
from kctl_ak.commands.flows import app as flows_app
from kctl_ak.commands.groups import app as groups_app
from kctl_ak.commands.health import app as health_app
from kctl_ak.commands.mail import app as mail_app
from kctl_ak.commands.maintenance import app as maintenance_app
from kctl_ak.commands.notifications import app as notifications_app
from kctl_ak.commands.outposts import app as outposts_app
from kctl_ak.commands.policies import app as policies_app
from kctl_ak.commands.property_mappings import app as property_mappings_app
from kctl_ak.commands.providers import app as providers_app
from kctl_ak.commands.sessions import app as sessions_app
from kctl_ak.commands.setup import app as setup_app
from kctl_ak.commands.stages import app as stages_app
from kctl_ak.commands.system import app as system_app
from kctl_ak.commands.tokens import app as tokens_app
from kctl_ak.commands.users import app as users_app
from kctl_ak.commands.provision import app as provision_app
from kctl_ak.core.callbacks import AppContext
from kctl_ak.commands.doctor_cmd import app as doctor_app
from kctl_ak.commands.skill_cmd import app as skill_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-ak {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-ak",
    help="Kodemeio Authentik CLI - manage your Authentik identity provider.",
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
    """Kodemeio Authentik CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        token_override=token,
    )


# Register all command groups
app.add_typer(users_app, name="users")
app.add_typer(groups_app, name="groups")
app.add_typer(apps_app, name="apps")
app.add_typer(providers_app, name="providers")
app.add_typer(flows_app, name="flows")
app.add_typer(audit_app, name="audit")
app.add_typer(sessions_app, name="sessions")
app.add_typer(tokens_app, name="tokens")
app.add_typer(blueprints_app, name="blueprints")
app.add_typer(maintenance_app, name="maintenance")
app.add_typer(setup_app, name="setup")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(config_app, name="config")
app.add_typer(mail_app, name="mail")
app.add_typer(policies_app, name="policies")
app.add_typer(stages_app, name="stages")
app.add_typer(property_mappings_app, name="property-mappings")
app.add_typer(certificates_app, name="certificates")
app.add_typer(outposts_app, name="outposts")
app.add_typer(brands_app, name="brands")
app.add_typer(notifications_app, name="notifications")
app.add_typer(system_app, name="system")
app.add_typer(provision_app, name="provision")
app.add_typer(doctor_app, name="doctor")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-ak."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-ak", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-ak")
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
        path = install_completions("kctl-ak", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-ak", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
