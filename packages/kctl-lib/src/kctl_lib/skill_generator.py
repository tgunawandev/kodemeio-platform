"""Auto-generate Claude Code SKILL.md from a Typer CLI app.

Introspects the Typer app via Click's API to extract all command groups,
subcommands, help text, parameters, and docstring examples. Generates a
complete SKILL.md with auto-generated trigger patterns and staleness hash.

Usage in each CLI:
    from kctl_lib.skill_generator import generate_skill
    generate_skill(app, "kctl-next", "next-admin", "Next.js monorepo management")

Improvements v2:
    - Extracts examples from docstrings (lines starting with whitespace after "Examples:")
    - Domain-specific triggers from group names and subcommand names
    - Staleness hash (command count + group names) embedded in frontmatter
    - check_stale() function to compare generated vs existing SKILL.md
"""

from __future__ import annotations

import hashlib
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

                # Extract examples from docstring
                examples = _extract_examples(sub_cmd.help or "")

                subcommands.append(
                    {
                        "name": sub_name,
                        "help": sub_cmd.help or "",
                        "params": params,
                        "examples": examples,
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


def _extract_examples(help_text: str) -> list[str]:
    """Extract example lines from a docstring.

    Looks for lines after "Examples:" that start with whitespace and
    contain the CLI name pattern (e.g., "kctl-odoo ...").
    """
    examples: list[str] = []
    in_examples = False

    for line in help_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("examples:") or stripped.lower().startswith("example:"):
            in_examples = True
            continue
        if in_examples:
            if stripped and (stripped.startswith("kctl-") or stripped.startswith("$")):
                examples.append(stripped)
            elif stripped and not line.startswith((" ", "\t")):
                # Non-indented non-empty line = end of examples section
                break

    return examples


def _generate_triggers(cli_name: str, groups: list[dict[str, Any]]) -> str:
    """Generate trigger patterns from command names, subcommand names, and help text."""
    triggers: set[str] = {f'"{cli_name}"'}

    for group in groups:
        # Add group name as trigger
        triggers.add(f'"{group["name"]}"')

        # Add subcommand names as triggers (domain-specific)
        for sub in group.get("subcommands", []):
            sub_name = sub.get("name", "")
            # Only add meaningful subcommand names (skip generic ones)
            if (
                sub_name not in ("list", "get", "create", "update", "delete", "show", "run", "status")
                and len(sub_name) > 3
            ):
                triggers.add(f'"{sub_name}"')

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
            "manufacturing",
            "warehouse",
            "helpdesk",
            "fleet",
            "compliance",
            "dunning",
            "budget",
            "quality",
            "approval",
            "invoice",
            "payment",
            "payroll",
            "attendance",
            "expense",
        ]:
            if word in help_text:
                triggers.add(f'"{word}"')

    # Sort and limit to avoid overly long trigger lists
    sorted_triggers = sorted(triggers)
    if len(sorted_triggers) > 80:
        sorted_triggers = sorted_triggers[:80]

    return ", ".join(sorted_triggers)


def _compute_hash(groups: list[dict[str, Any]]) -> str:
    """Compute a hash of group names + command counts for staleness detection."""
    parts = []
    for g in groups:
        sub_count = len(g.get("subcommands", []))
        parts.append(f"{g['name']}:{sub_count}")
    raw = "|".join(sorted(parts))
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def check_stale(
    typer_app: typer.Typer,
    skill_file: Path,
) -> tuple[bool, str]:
    """Check if a SKILL.md is stale compared to the current CLI.

    Returns:
        (is_stale, reason) — True if regeneration is needed.
    """
    if not skill_file.exists():
        return True, "SKILL.md does not exist"

    groups = _introspect_app(typer_app)
    current_hash = _compute_hash(groups)
    total_commands = sum(len(g.get("subcommands", [])) or 1 for g in groups)

    content = skill_file.read_text()

    # Check for hash in frontmatter
    for line in content.splitlines():
        if line.strip().startswith("registry_hash:"):
            existing_hash = line.split(":", 1)[1].strip()
            if existing_hash == current_hash:
                return False, f"Up to date (hash: {current_hash})"
            return True, f"Hash mismatch: {existing_hash} (file) vs {current_hash} (current)"

    # No hash found — check command count as fallback
    for line in content.splitlines():
        if "Total commands:" in line or "~" in line:
            if f"~{total_commands}" in line:
                return False, f"Command count matches (~{total_commands})"
            return True, f"Command count changed (current: ~{total_commands})"

    return True, "No hash or count found in existing SKILL.md"


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
    registry_hash = _compute_hash(groups)

    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f"name: {skill_name}")
    lines.append("description: >")
    lines.append(f"  {description} ({len(groups)} groups, ~{total_commands} commands).")
    lines.append(f"  MUST use for ANY {cli_name} operation.")
    lines.append(f"  Triggers on: {triggers}.")
    lines.append(f"  Auto-generated: {datetime.now(UTC).strftime('%Y-%m-%d')}")
    lines.append(f"  registry_hash: {registry_hash}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {skill_name} — {cli_name} CLI Reference")
    lines.append("")
    lines.append(f"> Auto-generated from `{cli_name}` command registry. Do not edit manually.")
    lines.append(f"> To regenerate: `{cli_name} skill generate`")
    lines.append("> To add custom content: edit `SKILL.extra.md` in the same directory.")
    lines.append("")

    # Quick stats
    lines.append("## Overview")
    lines.append("")
    lines.append(f"**CLI:** `{cli_name}`")
    lines.append(f"**Command groups:** {len(groups)}")
    lines.append(f"**Total commands:** ~{total_commands}")
    lines.append("**Install:** `cd cli && uv tool install --editable .`")
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
            # Only include first paragraph of help (before Examples:)
            help_first = group["help"].split("\n\n")[0].strip()
            # Also strip everything from "Examples:" onwards
            if "Examples:" in help_first:
                help_first = help_first[: help_first.index("Examples:")].strip()
            if "Example:" in help_first:
                help_first = help_first[: help_first.index("Example:")].strip()
            lines.append(f"{help_first}")
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

                # Truncate help to first sentence for table
                sub_help = sub.get("help", "")
                first_sentence = sub_help.split("\n\n")[0].split(". ")[0]
                if first_sentence and not first_sentence.endswith("."):
                    first_sentence += "."
                # Strip "Examples:" section from help
                if "Examples:" in first_sentence:
                    first_sentence = first_sentence[: first_sentence.index("Examples:")].strip()
                if "Example:" in first_sentence:
                    first_sentence = first_sentence[: first_sentence.index("Example:")].strip()

                lines.append(f"| `{group['name']} {sub['name']}{param_str}` | {first_sentence} |")
            lines.append("")

            # Add examples section if any subcommand has examples
            group_examples = []
            for sub in subcommands:
                for ex in sub.get("examples", []):
                    group_examples.append(ex)
            if group_examples:
                lines.append("**Examples:**")
                lines.append("```bash")
                # Show max 5 examples per group
                for ex in group_examples[:5]:
                    lines.append(ex)
                lines.append("```")
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
