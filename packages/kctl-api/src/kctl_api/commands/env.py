"""Environment management commands for kctl-api.

Validate, diff, template, and sync .env files across the monorepo.
"""

from __future__ import annotations

import pathlib
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="env", help="Environment management — validate, diff, template, sync.", no_args_is_help=True)


def _parse_env_file(path: pathlib.Path) -> dict[str, str]:
    """Parse a .env file into a key-value dict, ignoring comments."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _find_env_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Find all .env files in the monorepo (apps/)."""
    found = []
    for env_file in root.rglob(".env"):
        # Skip .env inside .venv, node_modules, etc.
        parts = env_file.parts
        if any(p in parts for p in (".venv", "node_modules", "__pycache__", ".git")):
            continue
        found.append(env_file)
    return sorted(found)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
@app.command()
def validate(
    ctx: typer.Context,
    env_file: Annotated[str | None, typer.Option("--file", "-f", help="Path to .env file.")] = None,
) -> None:
    """Validate .env against .env.example — show missing and extra keys."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    env_path = pathlib.Path(env_file) if env_file else root / ".env"
    example_path = env_path.parent / ".env.example"

    if not env_path.exists():
        out.error(f".env not found: {env_path}")
        raise typer.Exit(1)

    if not example_path.exists():
        out.warn(f"No .env.example found at {example_path} — cannot validate.")
        env_keys = _parse_env_file(env_path)
        out.info(f"{env_path.name} has {len(env_keys)} keys.")
        return

    env_keys = _parse_env_file(env_path)
    example_keys = _parse_env_file(example_path)

    missing = sorted(example_keys.keys() - env_keys.keys())
    extra = sorted(env_keys.keys() - example_keys.keys())
    shared = sorted(example_keys.keys() & env_keys.keys())

    issues: list[dict] = []

    for key in missing:
        issues.append({"key": key, "status": "MISSING", "note": "In .env.example but not in .env"})

    # Check for empty values on required keys
    for key in shared:
        if not env_keys[key] and example_keys.get(key):
            issues.append({"key": key, "status": "EMPTY", "note": "Key exists but has no value"})

    if not issues and not extra:
        out.success(f"Validation passed — {len(shared)} keys match, {len(extra)} extra keys in .env.")
        return

    if issues:
        rows = [[i["key"], i["status"], i["note"]] for i in issues]
        out.table(
            title=f"Validation Issues ({len(issues)})",
            columns=[("Key", "bold"), ("Status", "red"), ("Note", "")],
            rows=rows,
            data_for_json=issues,
        )

    if extra:
        out.info(f"Extra keys in .env (not in .env.example): {', '.join(extra[:10])}")

    if issues:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------
@app.command()
def diff(
    ctx: typer.Context,
    file_a: Annotated[str | None, typer.Argument(help="First .env file path.")] = None,
    file_b: Annotated[str | None, typer.Argument(help="Second .env file path.")] = None,
) -> None:
    """Diff two .env files, or .env vs .env.example if no args given."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    path_a = pathlib.Path(file_a) if file_a else root / ".env.example"
    path_b = pathlib.Path(file_b) if file_b else root / ".env"

    if not path_a.exists():
        out.error(f"File not found: {path_a}")
        raise typer.Exit(1)
    if not path_b.exists():
        out.error(f"File not found: {path_b}")
        raise typer.Exit(1)

    keys_a = _parse_env_file(path_a)
    keys_b = _parse_env_file(path_b)

    all_keys = sorted(keys_a.keys() | keys_b.keys())
    diffs: list[dict] = []

    for key in all_keys:
        in_a = key in keys_a
        in_b = key in keys_b
        val_a = keys_a.get(key, "")
        val_b = keys_b.get(key, "")

        if not in_a:
            diffs.append({"key": key, "status": "added", "a": "", "b": val_b})
        elif not in_b:
            diffs.append({"key": key, "status": "removed", "a": val_a, "b": ""})
        elif val_a != val_b:
            diffs.append({"key": key, "status": "changed", "a": val_a[:40], "b": val_b[:40]})

    if not diffs:
        out.success(f"No differences between {path_a.name} and {path_b.name}.")
        return

    rows = [
        [
            d["key"],
            {
                "added": "[green]added[/green]",
                "removed": "[red]removed[/red]",
                "changed": "[yellow]changed[/yellow]",
            }.get(d["status"], d["status"]),
            d["a"],
            d["b"],
        ]
        for d in diffs
    ]
    out.table(
        title=f"Diff: {path_a.name} vs {path_b.name} ({len(diffs)} differences)",
        columns=[("Key", "bold"), ("Status", ""), (path_a.name, ""), (path_b.name, "")],
        rows=rows,
        data_for_json=diffs,
    )


# ---------------------------------------------------------------------------
# template
# ---------------------------------------------------------------------------
@app.command()
def template(
    ctx: typer.Context,
    source: Annotated[str | None, typer.Option("--source", "-s", help="Source .env file.")] = None,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output path (default: .env.example).")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite if exists.")] = False,
) -> None:
    """Generate .env.example from .env by stripping values."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    source_path = pathlib.Path(source) if source else root / ".env"
    output_path = pathlib.Path(output) if output else source_path.parent / ".env.example"

    if not source_path.exists():
        out.error(f"Source .env not found: {source_path}")
        raise typer.Exit(1)

    if output_path.exists() and not force:
        confirm = typer.confirm(f"Overwrite existing {output_path}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    lines: list[str] = []
    for line in source_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(line)
        elif "=" in stripped:
            key = stripped.split("=")[0].strip()
            lines.append(f"{key}=")
        else:
            lines.append(line)

    output_path.write_text("\n".join(lines) + "\n")
    out.success(
        f"Template written to {output_path} ({len([ln for ln in lines if '=' in ln and not ln.startswith('#')])} keys)"
    )


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------
@app.command()
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be synced without writing.")] = False,
) -> None:
    """Sync .env keys across monorepo apps — add missing keys from root .env.example."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    root_example = root / ".env.example"

    if not root_example.exists():
        out.error(f"Root .env.example not found: {root_example}")
        raise typer.Exit(1)

    root_keys = _parse_env_file(root_example)
    env_files = _find_env_files(root)

    out.info(f"Root .env.example: {len(root_keys)} keys")
    out.info(f"Found {len(env_files)} .env files in monorepo")

    sync_report: list[dict] = []

    for env_file in env_files:
        example_file = env_file.parent / ".env.example"
        if not example_file.exists():
            sync_report.append({"file": str(env_file), "status": "no .env.example", "added": []})
            continue

        app_keys = _parse_env_file(example_file)
        missing_from_app = sorted(root_keys.keys() - app_keys.keys())

        if not missing_from_app:
            sync_report.append({"file": str(env_file), "status": "in sync", "added": []})
            continue

        if dry_run:
            sync_report.append({"file": str(env_file), "status": "needs sync", "added": missing_from_app})
            out.warn(f"Would add to {example_file.relative_to(root)}: {', '.join(missing_from_app)}")
        else:
            # Append missing keys (with empty values) to example
            with open(example_file, "a") as f:
                f.write("\n# Synced from root .env.example\n")
                for key in missing_from_app:
                    f.write(f"{key}=\n")
            sync_report.append({"file": str(env_file), "status": "synced", "added": missing_from_app})
            out.success(f"Synced {len(missing_from_app)} keys to {example_file.relative_to(root)}")

    rows = [
        [
            str(pathlib.Path(r["file"]).relative_to(root)),
            r["status"],
            str(len(r["added"])),
            ", ".join(r["added"][:5]),
        ]
        for r in sync_report
    ]
    out.table(
        title="Sync Report",
        columns=[("File", ""), ("Status", ""), ("Added", ""), ("Keys", "")],
        rows=rows,
        data_for_json=sync_report,
    )
