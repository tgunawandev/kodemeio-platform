"""Main CLI entry point for kctl-rmm."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_rmm import __version__
from kctl_rmm.commands.agents import app as agents_app
from kctl_rmm.commands.alerts import app as alerts_app
from kctl_rmm.commands.checks import app as checks_app
from kctl_rmm.commands.clients import app as clients_app
from kctl_rmm.commands.config_cmd import app as config_app
from kctl_rmm.commands.dashboard import app as dashboard_app
from kctl_rmm.commands.doctor_cmd import app as doctor_app
from kctl_rmm.commands.drivers import app as drivers_app
from kctl_rmm.commands.health import app as health_app
from kctl_rmm.commands.linux import app as linux_app
from kctl_rmm.commands.maintenance import app as maintenance_app
from kctl_rmm.commands.patches import app as patches_app
from kctl_rmm.commands.remote import app as remote_app
from kctl_rmm.commands.rustdesk import app as rustdesk_app
from kctl_rmm.commands.scripts import app as scripts_app
from kctl_rmm.commands.services import app as services_app
from kctl_rmm.commands.skill_cmd import app as skill_app
from kctl_rmm.commands.software import app as software_app
from kctl_rmm.commands.tasks import app as tasks_app
from kctl_rmm.commands.winupdates import app as winupdates_app
from kctl_rmm.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-rmm {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-rmm",
    help="Kodemeio Tactical RMM CLI - manage remote monitoring and management.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[str, typer.Option("--format", help="Output format: pretty, json, csv, yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit table headers")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="X-API-KEY override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Tactical RMM CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or output_format == "json",
        quiet=quiet,
        profile=profile,
        format=output_format,
        no_header=no_header,
        url_override=url,
        api_key_override=api_key,
    )


# Register all command groups
app.add_typer(agents_app, name="agents")
app.add_typer(scripts_app, name="scripts")
app.add_typer(clients_app, name="clients")
app.add_typer(software_app, name="software")
app.add_typer(patches_app, name="patches")
app.add_typer(alerts_app, name="alerts")
app.add_typer(tasks_app, name="tasks")
app.add_typer(services_app, name="services")
app.add_typer(drivers_app, name="drivers")
app.add_typer(remote_app, name="remote")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(doctor_app, name="doctor")
app.add_typer(maintenance_app, name="maintenance")
app.add_typer(config_app, name="config")
app.add_typer(checks_app, name="checks")
app.add_typer(winupdates_app, name="winupdates")
app.add_typer(linux_app, name="linux")
app.add_typer(rustdesk_app, name="rustdesk")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-rmm."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-rmm", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-rmm")
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
        path = install_completions("kctl-rmm", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-rmm", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with unified kctl-lib error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(130) from None


if __name__ == "__main__":
    _run()
