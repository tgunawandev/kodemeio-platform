"""Auto-generate Claude Code SKILL.md from a Typer CLI app.

Introspects the Typer app via Click's API to extract all command groups,
subcommands, help text, and parameters. Generates a complete SKILL.md
with auto-generated trigger patterns.

Usage in each CLI:
    from kctl_common.skill_generator import generate_skill
    generate_skill(app, "kctl-next", "next-admin", "Next.js monorepo management")
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer


def _introspect_app(typer_app: typer.Typer) -> list[dict[str, Any]]:
    """Extract command groups and subcommands from a Typer app."""
    click_app = typer.main.get_command(typer_app)
    groups: list[dict[str, Any]] = []

    if not hasattr(click_app, "commands"):
        return groups

    for name in sorted(click_app.commands.keys()):
        cmd = click_app.commands[name]
        group_info: dict[str, Any] = {
            "name": name,
            "help": cmd.help or "",
        }

        if hasattr(cmd, "commands"):
            # It's a group with subcommands
            subcommands: list[dict[str, Any]] = []
            for sub_name in sorted(cmd.commands.keys()):
                sub_cmd = cmd.commands[sub_name]
                params = []
                for p in sub_cmd.params:
                    if p.name in ("ctx", "help"):
                        continue
                    param_info = {
                        "name": p.name,
                        "required": p.required,
                        "type": p.type.name if hasattr(p.type, "name") else str(p.type),
                    }
                    params.append(param_info)
                subcommands.append(
                    {
                        "name": sub_name,
                        "help": sub_cmd.help or "",
                        "params": params,
                    }
                )
            group_info["subcommands"] = subcommands
        else:
            # It's a standalone command
            params = []
            for p in cmd.params:
                if p.name in ("ctx", "help"):
                    continue
                params.append({"name": p.name, "required": p.required})
            group_info["params"] = params
            group_info["subcommands"] = []

        groups.append(group_info)

    return groups


def _generate_triggers(cli_name: str, groups: list[dict]) -> str:
    """Generate trigger patterns from command names and help text."""
    triggers: list[str] = [f'"{cli_name}"']

    for group in groups:
        triggers.append(f'"{group["name"]}"')
        # Extract key words from help text
        help_text = group.get("help", "").lower()
        for word in [
            "audit",
            "validate",
            "check",
            "test",
            "debug",
            "profile",
            "deploy",
            "build",
            "lint",
            "security",
            "monitor",
            "health",
            "cache",
            "bundle",
            "migration",
            "backup",
            "restore",
        ]:
            if word in help_text:
                triggers.append(f'"{word}"')

    return ", ".join(sorted(set(triggers)))


def generate_skill(
    typer_app: typer.Typer,
    cli_name: str,
    skill_name: str,
    description: str,
    output_dir: Path | None = None,
    extra_file: Path | None = None,
) -> str:
    """Generate a SKILL.md file from a Typer app.

    Args:
        typer_app: The Typer application to introspect.
        cli_name: CLI binary name (e.g., "kctl-next").
        skill_name: Skill identifier (e.g., "next-admin").
        description: Short description for the skill.
        output_dir: Directory to write SKILL.md to. If None, returns string only.
        extra_file: Optional SKILL.extra.md to append (handwritten examples/guides).

    Returns:
        The generated SKILL.md content.
    """
    groups = _introspect_app(typer_app)
    total_commands = sum(len(g.get("subcommands", [])) or 1 for g in groups)
    triggers = _generate_triggers(cli_name, groups)

    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f"name: {skill_name}")
    lines.append(f"description: >")
    lines.append(f"  {description} ({len(groups)} groups, ~{total_commands} commands).")
    lines.append(f"  MUST use for ANY {cli_name} operation.")
    lines.append(f"  Triggers on: {triggers}.")
    lines.append(f"  Auto-generated: {datetime.now(UTC).strftime('%Y-%m-%d')}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {skill_name} — {cli_name} CLI Reference")
    lines.append("")
    lines.append(f"> Auto-generated from `{cli_name}` command registry. Do not edit manually.")
    lines.append(f"> To regenerate: `{cli_name} skill generate`")
    lines.append(f"> To add custom content: edit `SKILL.extra.md` in the same directory.")
    lines.append("")

    # Quick stats
    lines.append(f"## Overview")
    lines.append("")
    lines.append(f"**CLI:** `{cli_name}`")
    lines.append(f"**Command groups:** {len(groups)}")
    lines.append(f"**Total commands:** ~{total_commands}")
    lines.append(f"**Install:** `cd cli && uv tool install --editable .`")
    lines.append("")

    # Global options
    lines.append("## Global Options")
    lines.append("")
    lines.append("| Flag | Description |")
    lines.append("|------|-------------|")
    lines.append("| `--json` | JSON output |")
    lines.append("| `--quiet`, `-q` | Suppress info messages |")
    lines.append("| `--format`, `-f` | Output format: pretty/json/csv/yaml |")
    lines.append("| `--no-header` | Omit CSV header row |")
    lines.append("| `--profile`, `-p` | Config profile name |")
    lines.append("| `--version`, `-V` | Show version |")
    lines.append("")

    # Command reference
    lines.append("## Command Reference")
    lines.append("")

    for group in groups:
        lines.append(f"### `{cli_name} {group['name']}`")
        lines.append("")
        if group["help"]:
            lines.append(f"{group['help']}")
            lines.append("")

        subcommands = group.get("subcommands", [])
        if subcommands:
            lines.append("| Command | Description |")
            lines.append("|---------|-------------|")
            for sub in subcommands:
                param_str = ""
                if sub.get("params"):
                    param_parts = []
                    for p in sub["params"]:
                        if p.get("required"):
                            param_parts.append(f"<{p['name']}>")
                        else:
                            param_parts.append(f"[--{p['name']}]")
                    param_str = " " + " ".join(param_parts)
                lines.append(f"| `{group['name']} {sub['name']}{param_str}` | {sub['help']} |")
            lines.append("")
        else:
            params = group.get("params", [])
            if params:
                param_str = " ".join(f"<{p['name']}>" if p.get("required") else f"[--{p['name']}]" for p in params)
                lines.append(f"Usage: `{cli_name} {group['name']} {param_str}`")
                lines.append("")

    # Config section
    lines.append("## Configuration")
    lines.append("")
    lines.append("Shared config: `~/.config/kodemeio/config.yaml`")
    lines.append("")
    lines.append("```bash")
    lines.append(f"{cli_name} config init       # Interactive setup")
    lines.append(f"{cli_name} config show       # Show current config")
    lines.append(f"{cli_name} config profiles   # List profiles")
    lines.append(f"{cli_name} config current    # Show active profile")
    lines.append(f"{cli_name} config validate   # Verify config")
    lines.append("```")
    lines.append("")

    # Append extra content if exists
    if extra_file and extra_file.exists():
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(extra_file.read_text())

    content = "\n".join(lines)

    # Write to file
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        skill_file = output_dir / "SKILL.md"
        skill_file.write_text(content)

    return content
