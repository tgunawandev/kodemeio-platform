#!/usr/bin/env python3
"""Generate markdown CLI reference docs for all kctl-* packages.

Iterates over packages/kctl-*/src/kctl_*/cli.py, imports each CLI's Typer app,
introspects it via kctl_lib.skill_generator._introspect_app, and writes a
markdown command reference per CLI into docs/cli/.

Usage:
    uv run python scripts/generate-cli-docs.py
"""

from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the workspace packages are importable
ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
DOCS_DIR = ROOT / "docs" / "cli"


def _discover_cli_packages() -> list[tuple[str, str, Path]]:
    """Discover all kctl-* packages and return (pkg_dir_name, module_name, cli_path).

    Example: ("kctl-grafana", "kctl_grafana", .../cli.py)
    """
    results: list[tuple[str, str, Path]] = []
    for pkg_dir in sorted(PACKAGES_DIR.iterdir()):
        if not pkg_dir.is_dir() or not pkg_dir.name.startswith("kctl-"):
            continue
        # Skip kctl-lib (it's the shared library, not a CLI)
        if pkg_dir.name == "kctl-lib":
            continue

        module_name = pkg_dir.name.replace("-", "_")
        cli_path = pkg_dir / "src" / module_name / "cli.py"
        if cli_path.exists():
            results.append((pkg_dir.name, module_name, cli_path))
    return results


def _ensure_sys_path(pkg_dir_name: str) -> None:
    """Add the package src directory to sys.path if not already present."""
    src_dir = str(PACKAGES_DIR / pkg_dir_name / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def _import_app(module_name: str) -> object | None:
    """Import the Typer app from a CLI module. Returns None on failure."""
    full_module = f"{module_name}.cli"
    try:
        # Remove cached module to get a fresh import
        if full_module in sys.modules:
            del sys.modules[full_module]
        mod = importlib.import_module(full_module)
        return getattr(mod, "app", None)
    except Exception as exc:
        print(f"  WARNING: Could not import {full_module}: {exc}")
        return None


def _generate_cli_doc(
    cli_name: str,
    groups: list[dict],
) -> str:
    """Generate markdown documentation for a single CLI."""
    total_commands = sum(len(g.get("subcommands", [])) or 1 for g in groups)
    lines: list[str] = []

    lines.append(f"# {cli_name}")
    lines.append("")
    lines.append(
        f"Command reference for `{cli_name}` ({len(groups)} groups, ~{total_commands} commands)."
    )
    lines.append("")
    lines.append(
        f"> Auto-generated on {datetime.now(UTC).strftime('%Y-%m-%d')}. Do not edit manually."
    )
    lines.append("> Regenerate with: `uv run python scripts/generate-cli-docs.py`")
    lines.append("")

    # Global options
    lines.append("## Global Options")
    lines.append("")
    lines.append("| Flag | Description |")
    lines.append("|------|-------------|")
    lines.append("| `--json` | JSON output |")
    lines.append("| `--quiet`, `-q` | Suppress info messages |")
    lines.append("| `--format`, `-f` | Output format: pretty/json/csv/yaml |")
    lines.append("| `--no-header` | Omit headers in CSV output |")
    lines.append("| `--profile`, `-p` | Config profile name |")
    lines.append("| `--version`, `-V` | Show version |")
    lines.append("")

    # Command groups
    lines.append("## Commands")
    lines.append("")

    for group in groups:
        lines.append(f"### `{cli_name} {group['name']}`")
        lines.append("")
        if group.get("help"):
            help_text = group["help"].split("\n\n")[0].strip()
            # Strip examples section
            for marker in ("Examples:", "Example:"):
                if marker in help_text:
                    help_text = help_text[: help_text.index(marker)].strip()
            if help_text:
                lines.append(help_text)
                lines.append("")

        subcommands = group.get("subcommands", [])
        if subcommands:
            lines.append("| Command | Description |")
            lines.append("|---------|-------------|")
            for sub in subcommands:
                # Build parameter hint
                param_parts = []
                for p in sub.get("params", []):
                    if p.get("required"):
                        param_parts.append(f"<{p['name']}>")
                    else:
                        param_parts.append(f"[--{p['name']}]")
                param_str = (" " + " ".join(param_parts)) if param_parts else ""

                # First sentence of help
                sub_help = sub.get("help", "")
                first_sentence = sub_help.split("\n\n")[0].split(". ")[0]
                if first_sentence and not first_sentence.endswith("."):
                    first_sentence += "."
                for marker in ("Examples:", "Example:"):
                    if marker in first_sentence:
                        first_sentence = first_sentence[
                            : first_sentence.index(marker)
                        ].strip()

                lines.append(
                    f"| `{group['name']} {sub['name']}{param_str}` | {first_sentence} |"
                )
            lines.append("")

    return "\n".join(lines)


def _generate_index(entries: list[tuple[str, int, int]]) -> str:
    """Generate the docs/cli/README.md index.

    entries: list of (cli_name, group_count, command_count)
    """
    lines: list[str] = []
    lines.append("# CLI Reference Index")
    lines.append("")
    lines.append(f"Auto-generated on {datetime.now(UTC).strftime('%Y-%m-%d')}.")
    lines.append("Regenerate with: `uv run python scripts/generate-cli-docs.py`")
    lines.append("")

    total_clis = len(entries)
    total_groups = sum(g for _, g, _ in entries)
    total_cmds = sum(c for _, _, c in entries)
    lines.append(
        f"**{total_clis} CLIs** | **{total_groups} command groups** | **~{total_cmds} total commands**"
    )
    lines.append("")

    lines.append("| CLI | Groups | Commands | Reference |")
    lines.append("|-----|--------|----------|-----------|")
    for cli_name, groups, cmds in entries:
        doc_file = f"{cli_name}.md"
        lines.append(
            f"| `{cli_name}` | {groups} | ~{cmds} | [{doc_file}]({doc_file}) |"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    # Add kctl-lib to sys.path so all CLIs can import it
    kctl_lib_src = str(PACKAGES_DIR / "kctl-lib" / "src")
    if kctl_lib_src not in sys.path:
        sys.path.insert(0, kctl_lib_src)

    from kctl_lib.skill_generator import _introspect_app

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    packages = _discover_cli_packages()
    print(f"Found {len(packages)} CLI packages")

    index_entries: list[tuple[str, int, int]] = []
    generated = 0
    skipped = 0

    for pkg_dir_name, module_name, cli_path in packages:
        cli_name = pkg_dir_name  # e.g., "kctl-grafana"
        print(f"  Processing {cli_name}...", end=" ")

        _ensure_sys_path(pkg_dir_name)
        app = _import_app(module_name)

        if app is None:
            print("SKIPPED (no app found)")
            skipped += 1
            continue

        try:
            groups = _introspect_app(app)
        except Exception as exc:
            print(f"SKIPPED (introspection error: {exc})")
            skipped += 1
            continue

        total_commands = sum(len(g.get("subcommands", [])) or 1 for g in groups)
        doc_content = _generate_cli_doc(cli_name, groups)
        doc_path = DOCS_DIR / f"{cli_name}.md"
        doc_path.write_text(doc_content)

        index_entries.append((cli_name, len(groups), total_commands))
        generated += 1
        print(f"OK ({len(groups)} groups, ~{total_commands} commands)")

    # Write index
    index_content = _generate_index(index_entries)
    index_path = DOCS_DIR / "README.md"
    index_path.write_text(index_content)

    print(f"\nDone: {generated} generated, {skipped} skipped")
    print(f"Output: {DOCS_DIR}/")


if __name__ == "__main__":
    main()
