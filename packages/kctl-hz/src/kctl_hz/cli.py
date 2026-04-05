"""Main CLI entry point for kctl-hz."""

from __future__ import annotations

from pathlib import Path

from typing import Annotated

import typer
from kctl_lib import handle_cli_error
from kctl_lib.exceptions import KctlError

from kctl_hz import __version__
from kctl_hz.commands.aliases import register_aliases
from kctl_hz.commands.config_cmd import app as config_app
from kctl_hz.commands.costs import app as costs_app
from kctl_hz.commands.dns import app as dns_app
from kctl_hz.commands.firewalls import app as firewalls_app
from kctl_hz.commands.health import app as health_app
from kctl_hz.commands.images import app as images_app
from kctl_hz.commands.ips import app as ips_app
from kctl_hz.commands.labels import app as labels_app
from kctl_hz.commands.load_balancers import app as load_balancers_app
from kctl_hz.commands.locations import app as locations_app
from kctl_hz.commands.networks import app as networks_app
from kctl_hz.commands.placement_groups import app as placement_groups_app
from kctl_hz.commands.rdns import app as rdns_app
from kctl_hz.commands.s3 import app as s3_app
from kctl_hz.commands.self_test import app as self_test_app
from kctl_hz.commands.server_types import app as server_types_app
from kctl_hz.commands.servers import app as servers_app
from kctl_hz.commands.snapshots import app as snapshots_app
from kctl_hz.commands.ssh_keys import app as ssh_keys_app
from kctl_hz.commands.status import app as status_app
from kctl_hz.commands.storage_boxes import app as storage_boxes_app
from kctl_hz.commands.volumes import app as volumes_app
from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-hz {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-hz",
    help="Kodemeio Hetzner CLI - manage cloud servers, volumes, firewalls, DNS.",
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
    format: Annotated[str, typer.Option("--format", help="Output format: pretty, json, csv, yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit column headers in CSV output")] = False,
    token: Annotated[str | None, typer.Option("--token", help="Cloud API token override")] = None,
    dns_token: Annotated[str | None, typer.Option("--dns-token", help="DNS API token override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Hetzner CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        token_override=token,
        dns_token_override=dns_token,
    )


# --- Command groups ---
app.add_typer(config_app, name="config")
app.add_typer(servers_app, name="servers")
app.add_typer(status_app, name="status")
app.add_typer(health_app, name="health")
app.add_typer(volumes_app, name="volumes")
app.add_typer(firewalls_app, name="firewalls")
app.add_typer(networks_app, name="networks")
app.add_typer(ssh_keys_app, name="ssh-keys")
app.add_typer(ips_app, name="ips")
app.add_typer(snapshots_app, name="snapshots")
app.add_typer(load_balancers_app, name="load-balancers")
app.add_typer(dns_app, name="dns")
app.add_typer(costs_app, name="costs")
app.add_typer(placement_groups_app, name="placement-groups")
app.add_typer(s3_app, name="s3")
app.add_typer(server_types_app, name="server-types")
app.add_typer(locations_app, name="locations")
app.add_typer(images_app, name="images")
app.add_typer(labels_app, name="labels")
app.add_typer(rdns_app, name="rdns")
app.add_typer(storage_boxes_app, name="storage-boxes")
app.add_typer(self_test_app, name="self-test")

# --- Aliases ---
register_aliases(app)

# --- Plugins ---
discover_and_load_plugins(app)


# ---------------------------------------------------------------------------
# Skill generation
# ---------------------------------------------------------------------------
skill_app = typer.Typer(help="Skill management", hidden=True)


@skill_app.command()
def generate(
    output_dir: Annotated[
        str,
        typer.Option("--output", "-o", help="Output directory"),
    ] = str(Path.home() / ".claude" / "skills" / "hetzner-admin"),
) -> None:
    """Regenerate SKILL.md from current CLI commands."""
    from kctl_lib.skill_generator import generate_skill

    out_path = Path(output_dir)
    extra = Path(__file__).parent / "SKILL.extra.md"
    content = generate_skill(
        app,
        "kctl-hz",
        "hetzner-admin",
        "Hetzner Cloud infrastructure administration via kctl-hz CLI",
        output_dir=out_path,
        extra_file=extra if extra.exists() else None,
    )
    print(f"Generated SKILL.md at {out_path / 'SKILL.md'}")
    print(f"Commands: {content.count('|') // 2} entries")


app.add_typer(skill_app, name="skill")


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
