"""`kctl-profiles list` — enumerate profiles and their services."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kctl_lib.config import load_config

console = Console()


def list_profiles() -> None:
    """List every profile with its service keys."""
    cfg = load_config()
    if not cfg.profiles:
        console.print("[yellow]No profiles configured.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title="kctl-* profiles")
    table.add_column("Profile", style="bold cyan")
    table.add_column("Services", style="white")

    for name in sorted(cfg.profiles):
        data = cfg.profiles[name]
        services = sorted(k for k, v in data.items() if isinstance(v, dict))
        table.add_row(name, ", ".join(services) if services else "(flat)")

    console.print(table)
