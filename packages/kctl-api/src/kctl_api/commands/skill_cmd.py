"""Skill generation for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(help="Claude Code skill management.")


@app.command()
def generate(
    ctx: typer.Context,
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory")] = "",
    install: Annotated[bool, typer.Option("--install", help="Install to ~/.claude/skills/")] = False,
) -> None:
    """Auto-generate SKILL.md from CLI command registry."""
    actx: AppContext = ctx.obj
    out = actx.output
    from kctl_lib.skill_generator import generate_skill

    from kctl_api.cli import app as cli_app

    skill_name = "api-admin"
    description = "FastAPI platform management via kctl-api CLI"

    # Determine output directory
    if output:
        output_dir = Path(output)
    elif install:
        output_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        # Use CLI package root as base (3 levels up from this file: commands/ -> kctl_api/ -> src/ -> cli/)
        cli_root = Path(__file__).resolve().parents[3]
        output_dir = cli_root / "skills" / skill_name

    # Check for extra content
    extra = output_dir / "SKILL.extra.md"

    generate_skill(
        cli_app,
        "kctl-api",
        skill_name,
        description,
        output_dir=output_dir,
        extra_file=extra if extra.exists() else None,
    )
    out.success(f"Generated {output_dir / 'SKILL.md'}")
    if install:
        out.success(f"Installed to ~/.claude/skills/{skill_name}/")
