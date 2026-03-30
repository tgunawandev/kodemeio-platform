"""Main CLI entry point for kctl-hetzner."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_common import handle_cli_error
from kctl_common.exceptions import KctlError

from kctl_hetzner import __version__
from kctl_hetzner.commands.aliases import register_aliases
from kctl_hetzner.commands.config_cmd import app as config_app
from kctl_hetzner.commands.costs import app as costs_app
from kctl_hetzner.commands.dns import app as dns_app
from kctl_hetzner.commands.firewalls import app as firewalls_app
from kctl_hetzner.commands.health import app as health_app
from kctl_hetzner.commands.images import app as images_app
from kctl_hetzner.commands.ips import app as ips_app
from kctl_hetzner.commands.labels import app as labels_app
from kctl_hetzner.commands.load_balancers import app as load_balancers_app
from kctl_hetzner.commands.locations import app as locations_app
from kctl_hetzner.commands.networks import app as networks_app
from kctl_hetzner.commands.placement_groups import app as placement_groups_app
from kctl_hetzner.commands.rdns import app as rdns_app
from kctl_hetzner.commands.s3 import app as s3_app
from kctl_hetzner.commands.self_test import app as self_test_app
from kctl_hetzner.commands.server_types import app as server_types_app
from kctl_hetzner.commands.servers import app as servers_app
from kctl_hetzner.commands.snapshots import app as snapshots_app
from kctl_hetzner.commands.ssh_keys import app as ssh_keys_app
from kctl_hetzner.commands.status import app as status_app
from kctl_hetzner.commands.storage_boxes import app as storage_boxes_app
from kctl_hetzner.commands.volumes import app as volumes_app
from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-hetzner {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-hetzner",
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


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
