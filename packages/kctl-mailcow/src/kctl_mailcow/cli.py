"""Main CLI entry point for kctl-mailcow."""

from __future__ import annotations

from pathlib import Path

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_mailcow import __version__
from kctl_mailcow.commands.alias_domains import app as alias_domains_app
from kctl_mailcow.commands.aliases import app as aliases_app
from kctl_mailcow.commands.app_passwords import app as app_passwords_app
from kctl_mailcow.commands.bcc_maps import app as bcc_maps_app
from kctl_mailcow.commands.config_cmd import app as config_app
from kctl_mailcow.commands.dashboard import app as dashboard_app
from kctl_mailcow.commands.dkim import app as dkim_app
from kctl_mailcow.commands.domain_admins import app as domain_admins_app
from kctl_mailcow.commands.domains import app as domains_app
from kctl_mailcow.commands.fail2ban import app as fail2ban_app
from kctl_mailcow.commands.filters import app as filters_app
from kctl_mailcow.commands.fwdhost import app as fwdhost_app
from kctl_mailcow.commands.health import app as health_app
from kctl_mailcow.commands.identity_provider import app as identity_provider_app
from kctl_mailcow.commands.logs import app as logs_app
from kctl_mailcow.commands.mailboxes import app as mailboxes_app
from kctl_mailcow.commands.oauth2_clients import app as oauth2_clients_app
from kctl_mailcow.commands.password_policy import app as password_policy_app
from kctl_mailcow.commands.policies import app as policies_app
from kctl_mailcow.commands.provision import app as provision_app
from kctl_mailcow.commands.quarantine import app as quarantine_app
from kctl_mailcow.commands.queue import app as queue_app
from kctl_mailcow.commands.ratelimits import app as ratelimits_app
from kctl_mailcow.commands.recipient_maps import app as recipient_maps_app
from kctl_mailcow.commands.relay_hosts import app as relay_hosts_app
from kctl_mailcow.commands.resources import app as resources_app
from kctl_mailcow.commands.rspamd import app as rspamd_app
from kctl_mailcow.commands.status import app as status_app
from kctl_mailcow.commands.sync_jobs import app as sync_jobs_app
from kctl_mailcow.commands.tls import app as tls_app
from kctl_mailcow.commands.transports import app as transports_app
from kctl_mailcow.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-mailcow {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-mailcow",
    help="Kodemeio Mailcow CLI - manage your Mailcow mail server.",
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
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Mailcow CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Register all command groups
app.add_typer(domains_app, name="domains")
app.add_typer(mailboxes_app, name="mailboxes")
app.add_typer(aliases_app, name="aliases")
app.add_typer(dkim_app, name="dkim")
app.add_typer(queue_app, name="queue")
app.add_typer(logs_app, name="logs")
app.add_typer(ratelimits_app, name="ratelimits")
app.add_typer(quarantine_app, name="quarantine")
app.add_typer(status_app, name="status")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(sync_jobs_app, name="sync-jobs")
app.add_typer(fwdhost_app, name="fwdhost")
app.add_typer(config_app, name="config")
app.add_typer(tls_app, name="tls")
app.add_typer(resources_app, name="resources")
# Phase 1: Authentik integration
app.add_typer(identity_provider_app, name="identity-provider")
app.add_typer(oauth2_clients_app, name="oauth2-clients")
app.add_typer(provision_app, name="provision")
# Phase 2: Security & compliance
app.add_typer(fail2ban_app, name="fail2ban")
app.add_typer(policies_app, name="policies")
app.add_typer(app_passwords_app, name="app-passwords")
app.add_typer(password_policy_app, name="password-policy")
app.add_typer(domain_admins_app, name="domain-admins")
app.add_typer(filters_app, name="filters")
# Phase 3: Routing & advanced
app.add_typer(transports_app, name="transports")
app.add_typer(relay_hosts_app, name="relay-hosts")
app.add_typer(bcc_maps_app, name="bcc-maps")
app.add_typer(alias_domains_app, name="alias-domains")
app.add_typer(recipient_maps_app, name="recipient-maps")
app.add_typer(rspamd_app, name="rspamd")


# ---------------------------------------------------------------------------
# Skill generation
# ---------------------------------------------------------------------------
skill_app = typer.Typer(help="Skill management", hidden=True)


@skill_app.command()
def generate(
    output_dir: Annotated[
        str,
        typer.Option("--output", "-o", help="Output directory"),
    ] = str(Path.home() / ".claude" / "skills" / "mailcow-admin"),
) -> None:
    """Regenerate SKILL.md from current CLI commands."""
    from kctl_lib.skill_generator import generate_skill

    out_path = Path(output_dir)
    extra = Path(__file__).parent / "SKILL.extra.md"
    content = generate_skill(
        app,
        "kctl-mailcow",
        "mailcow-admin",
        "Mailcow mail server administration via kctl-mailcow CLI",
        output_dir=out_path,
        extra_file=extra if extra.exists() else None,
    )
    print(f"Generated SKILL.md at {out_path / 'SKILL.md'}")
    print(f"Commands: {content.count('|') // 2} entries")


app.add_typer(skill_app, name="skill")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
