"""`kctl-profiles validate` — schema-check every registered service."""

from __future__ import annotations

import typer
from pydantic import ValidationError
from rich.console import Console

from kctl_lib.config import load_config
from kctl_lib.schemas import all_registered_schemas

console = Console()


def validate(
    profile: str | None = typer.Argument(None, help="Only validate this profile; omit to validate every profile."),
) -> None:
    """Run every registered service schema against every (or one) profile."""
    cfg = load_config()
    schemas = dict(all_registered_schemas())
    if not schemas:
        console.print("[yellow]No service schemas registered.[/yellow]")
        raise typer.Exit(code=0)

    profiles_to_check = {profile: cfg.profiles.get(profile, {})} if profile else cfg.profiles

    errors = 0
    for profile_name, profile_data in profiles_to_check.items():
        if not isinstance(profile_data, dict):
            continue
        for service_key, service_data in profile_data.items():
            schema = schemas.get(service_key)
            if schema is None or not isinstance(service_data, dict):
                continue
            try:
                schema.model_validate(service_data)
            except ValidationError as exc:
                errors += 1
                console.print(f"[red]✗ {profile_name}.{service_key}[/red]")
                for err in exc.errors():
                    loc = ".".join(str(p) for p in err["loc"])
                    console.print(f"  {loc}: {err['msg']}")

    if errors:
        console.print(f"\n[red]{errors} error(s).[/red]")
        raise typer.Exit(code=1)
    console.print("[green]OK — all profiles valid.[/green]")
