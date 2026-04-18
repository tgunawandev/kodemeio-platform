"""Main CLI entry point for kctl-react."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_react import __version__
from kctl_react.commands.a11y import app as a11y_app
from kctl_react.commands.affected import app as affected_app
from kctl_react.commands.apps import app as apps_app
from kctl_react.commands.build import app as build_app
from kctl_react.commands.bundle_cmd import app as bundle_app
from kctl_react.commands.cap import app as cap_app
from kctl_react.commands.clean import app as clean_app
from kctl_react.commands.compliance import app as compliance_app
from kctl_react.commands.codegen import app as codegen_app
from kctl_react.commands.config_cmd import app as config_app
from kctl_react.commands.dashboard import app as dashboard_app
from kctl_react.commands.deploy import app as deploy_app
from kctl_react.commands.deps import app as deps_app
from kctl_react.commands.dev import app as dev_app
from kctl_react.commands.docker_cmd import app as docker_app
from kctl_react.commands.doctor import app as doctor_app
from kctl_react.commands.e2e import app as e2e_app
from kctl_react.commands.env import app as env_app
from kctl_react.commands.i18n import app as i18n_app
from kctl_react.commands.lint import app as lint_app
from kctl_react.commands.maintenance import app as maintenance_app
from kctl_react.commands.monitor_cmd import app as monitor_app
from kctl_react.commands.observe import app as observe_app
from kctl_react.commands.packages import app as packages_app
from kctl_react.commands.perf import app as perf_app
from kctl_react.commands.pipeline import app as pipeline_app
from kctl_react.commands.pwa import app as pwa_app
from kctl_react.commands.scaffold import app as scaffold_app
from kctl_react.commands.security import app as security_app
from kctl_react.commands.skill_cmd import app as skill_app
from kctl_react.commands.state import app as state_app
from kctl_react.commands.test_cmd import app as test_app
from kctl_react.commands.ui_audit import app as ui_audit_app
from kctl_react.core.callbacks import AppContext
from kctl_react.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-react {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-react",
    help="Kodemeio React Monorepo CLI — manage Vite PWAs + Next.js apps + shared packages.",
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
    root: Annotated[str | None, typer.Option("--root", help="Monorepo root override")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit header row in CSV output")] = False,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio React Monorepo CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        root_override=root,
        format=format,
        no_header=no_header,
    )


@app.command("info")
def info_cmd(ctx: typer.Context) -> None:
    """Show monorepo summary: apps, packages, and CLI version."""

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info(f"kctl-react {__version__}")
    out.info(f"Root: {root}")
    apps = actx.apps
    vite_apps = [n for n, info in apps.items() if info.get("framework") == "vite"]
    next_apps = [n for n, info in apps.items() if info.get("framework") == "nextjs"]
    out.info(f"Apps ({len(apps)}): {len(vite_apps)} Vite + {len(next_apps)} Next.js")
    if vite_apps:
        out.info(f"  Vite: {', '.join(vite_apps)}")
    if next_apps:
        out.info(f"  Next.js: {', '.join(next_apps)}")
    packages = actx.packages
    out.info(f"Packages ({len(packages)}): {', '.join(packages)}")


# Register all command groups
app.add_typer(affected_app, name="affected")
app.add_typer(apps_app, name="apps")
app.add_typer(build_app, name="build")
app.add_typer(cap_app, name="cap")
app.add_typer(clean_app, name="clean")
app.add_typer(codegen_app, name="codegen")
app.add_typer(compliance_app, name="compliance")
app.add_typer(config_app, name="config")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(deploy_app, name="deploy")
app.add_typer(deps_app, name="deps")
app.add_typer(dev_app, name="dev")
app.add_typer(doctor_app, name="doctor")
app.add_typer(e2e_app, name="e2e")
app.add_typer(env_app, name="env")
app.add_typer(lint_app, name="lint")
app.add_typer(packages_app, name="packages")
app.add_typer(perf_app, name="perf")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(scaffold_app, name="scaffold")
app.add_typer(security_app, name="security")
app.add_typer(test_app, name="test")
app.add_typer(pwa_app, name="pwa")
app.add_typer(a11y_app, name="a11y")
app.add_typer(i18n_app, name="i18n")
app.add_typer(ui_audit_app, name="ui")
app.add_typer(state_app, name="state")
app.add_typer(bundle_app, name="bundle")
app.add_typer(observe_app, name="observe")
app.add_typer(docker_app, name="docker")
app.add_typer(monitor_app, name="monitor")
app.add_typer(maintenance_app, name="maintenance")
app.add_typer(skill_app, name="skill")

# Load third-party plugins via entry points
discover_and_load_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-react."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-react", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-react")
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
        path = install_completions("kctl-react", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-react", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
