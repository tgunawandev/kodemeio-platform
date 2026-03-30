"""Skill management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import NotFoundError

app = typer.Typer(help="Manage OpenClaw skills.")

_SKILL_TEMPLATE = """\
---
name: {name}
version: 1.0.0
description: ""
trigger: "/{name}"
---

# {name}

## Overview

Describe the skill here.

## Usage

Describe how to use the skill.
"""


def _skills_root(project_root: Path) -> Path:
    return project_root / "config" / "skills"


def _get_skill_dir(project_root: Path, name: str) -> Path:
    return _skills_root(project_root) / name


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all skills."""
    actx: AppContext = ctx.obj
    out = actx.output

    skills_dir = _skills_root(actx.project_root)
    if not skills_dir.exists():
        out.warn("Skills directory not found: config/skills/")
        return

    skills: list[dict[str, str | bool]] = []
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir():
            skill_md = d / "SKILL.md"
            has_md = skill_md.exists()
            size = f"{skill_md.stat().st_size:,} bytes" if has_md else "no SKILL.md"
            skills.append({"name": d.name, "has_skill_md": has_md, "size": size})

    rows: list[list[str]] = [
        [str(s["name"]), "yes" if s["has_skill_md"] else "[red]no[/red]", str(s["size"])] for s in skills
    ]
    out.table(
        f"Skills ({len(skills)})",
        [("Name", "cyan"), ("SKILL.md", ""), ("Size", "dim")],
        rows,
        data_for_json=skills,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Skill name")],
) -> None:
    """Read and print SKILL.md content."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _get_skill_dir(actx.project_root, name)
    if not skill_dir.exists():
        raise NotFoundError("Skill", name)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        out.warn(f"No SKILL.md found in {skill_dir}")
        return

    content = skill_md.read_text()
    if out.json_mode or out.format == "json":
        import json

        typer.echo(json.dumps({"name": name, "content": content}))
    else:
        typer.echo(content)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Skill name (slug, e.g. my-skill)")],
) -> None:
    """Create a new skill directory with SKILL.md template."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _get_skill_dir(actx.project_root, name)
    if skill_dir.exists():
        out.error(f"Skill already exists: {name!r}")
        raise typer.Exit(1)

    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(_SKILL_TEMPLATE.format(name=name))
    out.success(f"Created skill: config/skills/{name}/SKILL.md")
    out.info("Edit the file to fill in description and usage.")


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Skill name")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a skill directory."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _get_skill_dir(actx.project_root, name)
    if not skill_dir.exists():
        raise NotFoundError("Skill", name)

    if not yes:
        confirmed = typer.confirm(f"Delete skill {name!r} and all its files?")
        if not confirmed:
            out.info("Aborted.")
            return

    import shutil

    shutil.rmtree(skill_dir)
    out.success(f"Deleted skill: {name!r}")
