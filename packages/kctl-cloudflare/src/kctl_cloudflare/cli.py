"""Main CLI entry point for kctl-cloudflare."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare import __version__
from kctl_cloudflare.commands.access import app as access_app
from kctl_cloudflare.commands.analytics import app as analytics_app
from kctl_cloudflare.commands.argo import app as argo_app
from kctl_cloudflare.commands.cache import app as cache_app
from kctl_cloudflare.commands.config_cmd import app as config_app
from kctl_cloudflare.commands.custom_hostnames import app as custom_hostnames_app
from kctl_cloudflare.commands.email_routing import app as email_routing_app
from kctl_cloudflare.commands.export import app as export_app
from kctl_cloudflare.commands.health import app as health_app
from kctl_cloudflare.commands.load_balancers import app as load_balancers_app
from kctl_cloudflare.commands.page_rules import app as page_rules_app
from kctl_cloudflare.commands.pages import app as pages_app
from kctl_cloudflare.commands.r2 import app as r2_app
from kctl_cloudflare.commands.records import app as records_app
from kctl_cloudflare.commands.redirects import app as redirects_app
from kctl_cloudflare.commands.selftest import app as selftest_app
from kctl_cloudflare.commands.spectrum import app as spectrum_app
from kctl_cloudflare.commands.speed import app as speed_app
from kctl_cloudflare.commands.ssl import app as ssl_app
from kctl_cloudflare.commands.terraform import app as terraform_app
from kctl_cloudflare.commands.tunnels import app as tunnels_app
from kctl_cloudflare.commands.waf import app as waf_app
from kctl_cloudflare.commands.waiting_rooms import app as waiting_rooms_app
from kctl_cloudflare.commands.workers import app as workers_app
from kctl_cloudflare.commands.zones import app as zones_app
from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.exceptions import APIError, AuthenticationError, ConfigError, KctlError
from kctl_cloudflare.core.exceptions import ConnectionError as KctlConnectionError
from kctl_cloudflare.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-cloudflare {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-cloudflare",
    help="Kodemeio Cloudflare CLI - manage DNS, tunnels, WAF, cache, Workers, R2, email routing, access.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty/json/csv/yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit header row in CSV output")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    api_token: Annotated[str | None, typer.Option("--api-token", help="API token override")] = None,
    account_id: Annotated[str | None, typer.Option("--account-id", help="Account ID override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Cloudflare CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        format=format,
        no_header=no_header,
        profile=profile,
        api_token_override=api_token,
        account_id_override=account_id,
    )


app.add_typer(config_app, name="config")
app.add_typer(zones_app, name="zones")
app.add_typer(records_app, name="records")
app.add_typer(tunnels_app, name="tunnels")
app.add_typer(health_app, name="health")
app.add_typer(waf_app, name="waf")
app.add_typer(cache_app, name="cache")
app.add_typer(ssl_app, name="ssl")
app.add_typer(workers_app, name="workers")
app.add_typer(r2_app, name="r2")
app.add_typer(export_app, name="export")
app.add_typer(terraform_app, name="terraform")
app.add_typer(email_routing_app, name="email-routing")
app.add_typer(page_rules_app, name="page-rules")
app.add_typer(pages_app, name="pages")
app.add_typer(redirects_app, name="redirects")
app.add_typer(access_app, name="access")
app.add_typer(speed_app, name="speed")
app.add_typer(analytics_app, name="analytics")
app.add_typer(selftest_app, name="selftest")
app.add_typer(argo_app, name="argo")
app.add_typer(custom_hostnames_app, name="custom-hostnames")
app.add_typer(load_balancers_app, name="load-balancers")
app.add_typer(spectrum_app, name="spectrum")
app.add_typer(waiting_rooms_app, name="waiting-rooms")

# Load plugins from entry points
discover_and_load_plugins(app)

# Register short aliases
from kctl_cloudflare.commands.aliases import register_aliases  # noqa: E402

register_aliases(app)


def _run() -> None:
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
