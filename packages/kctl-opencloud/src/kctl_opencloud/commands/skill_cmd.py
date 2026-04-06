"""Skill generation command for kctl-opencloud."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Skill management.", hidden=True)


@app.command()
def generate(
    ctx: typer.Context,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output directory")] = None,
    install: Annotated[bool, typer.Option("--install", help="Install to user skills dir")] = False,
    check: Annotated[bool, typer.Option("--check", help="Check if skill is stale")] = False,
) -> None:
    """Generate Claude Code skill file."""
    from kctl_lib.skill_generator import check_stale, generate_skill

    from kctl_opencloud.cli import app as cli_app

    skill_name = "opencloud-admin"

    extra_path = Path(__file__).parent.parent.parent.parent / "skills" / skill_name / "SKILL.extra.md"
    extra_content = extra_path.read_text() if extra_path.exists() else None

    if check:
        if check_stale(skill_name, cli_app, extra_content=extra_content):
            typer.echo("Skill is stale — regenerate with: kctl-opencloud skill generate --install")
            raise typer.Exit(code=1)
        typer.echo("Skill is up to date")
        return

    if output:
        out_dir = Path(output)
    elif install:
        out_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        out_dir = Path(__file__).parent.parent.parent.parent / "skills" / skill_name

    generate_skill(
        skill_name=skill_name,
        cli_app=cli_app,
        output_dir=out_dir,
        extra_content=extra_content,
    )
    typer.echo(f"Skill generated at {out_dir}/SKILL.md")
