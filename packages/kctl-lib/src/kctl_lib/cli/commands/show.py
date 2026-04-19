"""`kctl-profiles show` — resolved profile view with masked secrets."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kctl_lib.config import load_config, resolve_inheritance_chain

console = Console()

SECRET_FIELDS: frozenset[str] = frozenset(
    {
        "token",
        "api_key",
        "password",
        "service_account_token",
        "auth_token",
        "signature_secret",
        "dns_token",
        "s3_secret_key",
    }
)


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _format_value(key: str, value: object, reveal: bool) -> str:
    if key in SECRET_FIELDS and isinstance(value, str) and not reveal:
        return _mask(value)
    return str(value)


def show_profile(
    profile: str = typer.Argument(..., help="Profile name to show."),
    reveal: bool = typer.Option(False, "--reveal", help="Show secrets in plaintext."),
) -> None:
    """Display a profile with inheritance resolved and secrets masked."""
    cfg = load_config()
    if profile not in cfg.profiles:
        console.print(f"[red]Profile not found:[/red] {profile}")
        raise typer.Exit(code=1)

    chain = resolve_inheritance_chain(profile)
    resolved: dict[str, tuple[str, dict]] = {}
    for name in chain:
        data = cfg.profiles.get(name, {})
        for svc, svc_data in data.items():
            if isinstance(svc_data, dict) and svc not in resolved:
                resolved[svc] = (name, svc_data)

    chain_str = "  ←  ".join(chain)
    console.print(f"[bold cyan]profile:[/bold cyan] {chain_str}")
    console.print()

    for svc in sorted(resolved):
        source, svc_data = resolved[svc]
        title = f"{svc}  [dim](from {source})[/dim]"
        table = Table(title=title, title_justify="left", show_header=False)
        table.add_column("key", style="bold")
        table.add_column("value")
        for k in sorted(svc_data):
            table.add_row(k, _format_value(k, svc_data[k], reveal))
        console.print(table)
        console.print()
