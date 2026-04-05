"""Skill generation for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_claude.core.callbacks import AppContext

app = typer.Typer(help="Claude Code skill management.")


@app.command()
def generate(
    ctx: typer.Context,
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory")] = "",
    install: Annotated[bool, typer.Option("--install", help="Install to ~/.claude/skills/")] = False,
    check: Annotated[bool, typer.Option("--check", help="Check if SKILL.md is stale (exit 1 if stale)")] = False,
) -> None:
    """Auto-generate SKILL.md from CLI command registry.

    Examples:
        kctl-claude skill generate
        kctl-claude skill generate --install
        kctl-claude skill generate --check
    """
    actx: AppContext = ctx.obj
    out = actx.output
    from kctl_lib.skill_generator import check_stale, generate_skill

    from kctl_claude.cli import app as cli_app

    skill_name = "claude-admin"
    description = "Claude Code environment management via kctl-claude CLI"

    # Determine output directory
    if output:
        output_dir = Path(output)
    elif install:
        output_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        cli_root = Path(__file__).resolve().parents[3]
        output_dir = cli_root / "skills" / skill_name

    # Check-only mode
    if check:
        skill_file = output_dir / "SKILL.md"
        is_stale, reason = check_stale(cli_app, skill_file)
        if is_stale:
            out.warn(f"SKILL.md is stale: {reason}")
            out.info("Run: kctl-claude skill generate")
            raise typer.Exit(1)
        out.success(f"SKILL.md is up to date: {reason}")
        return

    # Check for extra content
    extra = output_dir / "SKILL.extra.md"

    generate_skill(
        cli_app,
        "kctl-claude",
        skill_name,
        description,
        output_dir=output_dir,
        extra_file=extra if extra.exists() else None,
    )
    out.success(f"Generated {output_dir / 'SKILL.md'}")
    if install:
        out.success(f"Installed to ~/.claude/skills/{skill_name}/")
