#!/usr/bin/env python3
"""Generate command reference from kctl-odoo --help output.

Usage: python scripts/generate_skill_commands.py
Output: Prints markdown for all command groups to stdout.
"""

from __future__ import annotations

import re
import subprocess


def get_help(args: list[str]) -> str:
    """Run kctl-odoo with --help and return stdout."""
    result = subprocess.run(
        ["kctl-odoo", *args, "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout


def _parse_section(help_text: str, section: str = "Commands") -> list[tuple[str, str]]:
    """Extract (name, description) pairs from a specific help section."""
    items: list[tuple[str, str]] = []
    in_section = False
    for line in help_text.splitlines():
        if f"─ {section} " in line:
            in_section = True
            continue
        if in_section and "╰─" in line:
            break
        if in_section:
            m = re.match(r"\s*│\s+(\S+)\s{2,}(.+?)\s*│?$", line)
            if m:
                name = m.group(1).strip()
                desc = m.group(2).strip()
                if name != "--help":
                    items.append((name, desc))
    return items


def main() -> None:
    """Generate the full command reference as markdown."""
    top_help = get_help([])
    groups = _parse_section(top_help, "Commands")

    print(f"# kctl-odoo Command Reference ({len(groups)} groups)\n")

    total_commands = 0
    for group_name, _group_desc in groups:
        group_help = get_help([group_name])
        commands = _parse_section(group_help, "Commands")
        total_commands += len(commands)

        print(f"### {group_name} ({len(commands)} commands)")
        print("```bash")
        for cmd_name, cmd_desc in commands:
            desc = cmd_desc[:60] + "..." if len(cmd_desc) > 60 else cmd_desc
            print(f"kctl-odoo {group_name} {cmd_name:<25} # {desc}")
        print("```\n")

    print(f"\n**Total: {len(groups)} groups, {total_commands} commands**")


if __name__ == "__main__":
    main()
