"""`kctl-profiles current` — show the active profile and its source."""

from __future__ import annotations

import os

import typer
from rich.console import Console

from kctl_lib.config import resolve_active_profile_name

console = Console()


def current_profile(
    profile: str | None = typer.Option(None, "--profile", "-p"),
) -> None:
    """Print the active profile and where it came from."""
    env_var = "KCTL_PROFILES_PROFILE"
    try:
        resolved = resolve_active_profile_name(profile, "KCTL_PROFILES")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if profile:
        source = "--profile flag"
    elif os.environ.get(env_var):
        source = f"${env_var}"
    else:
        source = "(unknown)"

    console.print(f"[bold cyan]profile:[/bold cyan] {resolved}")
    console.print(f"[dim]source:[/dim] {source}")
