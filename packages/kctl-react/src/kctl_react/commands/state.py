"""State management analysis — TanStack Query static analysis."""

from __future__ import annotations

import contextlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.analyzers import find_hook_files, find_query_keys
from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="TanStack Query static analysis (query keys, hooks audit, invalidation map).")


@app.command("query-keys")
def query_keys(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """List all TanStack Query queryKey definitions in hook files and inline queries."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.project_root / "apps" / app_name / "src"

    results: list[dict] = []

    # Scan hook files
    for hook_file in find_hook_files(src_dir):
        for entry in find_query_keys(hook_file):
            entry = dict(entry)
            with contextlib.suppress(ValueError):
                entry["file"] = str(Path(str(entry["file"])).relative_to(actx.project_root))
            results.append(entry)

    # Also scan .tsx files for inline queries
    for tsx_file in src_dir.rglob("*.tsx"):
        for entry in find_query_keys(tsx_file):
            entry = dict(entry)
            with contextlib.suppress(ValueError):
                entry["file"] = str(Path(str(entry["file"])).relative_to(actx.project_root))
            results.append(entry)

    if not results:
        out.warn(f"No queryKey definitions found in {app_name}")
        return

    rows = [[r["file"], str(r["line"]), r["key_prefix"]] for r in results]
    out.table(
        f"Query Keys ({len(results)} found in {app_name})",
        [("File", "cyan"), ("Line", "dim"), ("Key Prefix", "green")],
        rows,
        data_for_json=results,
    )


@app.command("consistency")
def consistency(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Check query key consistency — duplicates and mutations missing invalidation."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.project_root / "apps" / app_name / "src"

    # Collect query keys grouped by prefix and the hook files they appear in
    prefix_to_files: dict[str, set[str]] = defaultdict(set)
    for hook_file in find_hook_files(src_dir):
        for entry in find_query_keys(hook_file):
            prefix = str(entry["key_prefix"])
            prefix_to_files[prefix].add(hook_file.name)

    issues: list[dict] = []

    # Check: same prefix in multiple hook files (possible duplication)
    for prefix, files in sorted(prefix_to_files.items()):
        if len(files) > 1:
            issues.append(
                {
                    "type": "duplicate_prefix",
                    "prefix": prefix,
                    "detail": f"Appears in {len(files)} files: {', '.join(sorted(files))}",
                }
            )

    # Check: mutations without invalidateQueries
    for hook_file in find_hook_files(src_dir):
        try:
            text = hook_file.read_text()
        except OSError:
            continue
        # Find mutation functions (useCreate*, useUpdate*, useDelete*)
        mutation_pattern = re.compile(r"export\s+function\s+(use(?:Create|Update|Delete)\w+)")
        for match in mutation_pattern.finditer(text):
            fn_name = match.group(1)
            # Find the function body (simple heuristic: text from match to next export)
            start = match.start()
            # Check if invalidateQueries appears after this mutation definition
            fn_region = text[start : start + 600]
            if "invalidateQueries" not in fn_region:
                issues.append(
                    {
                        "type": "missing_invalidation",
                        "prefix": fn_name,
                        "detail": f"Mutation in {hook_file.name} has no invalidateQueries",
                    }
                )

    if not issues:
        out.success(f"Query key consistency OK for {app_name}")
        return

    rows = [[i["type"], i["prefix"], i["detail"]] for i in issues]
    out.table(
        f"Consistency Issues ({len(issues)} found in {app_name})",
        [("Type", "yellow"), ("Prefix/Function", "red"), ("Detail", "dim")],
        rows,
        data_for_json=issues,
    )


@app.command("hooks-audit")
def hooks_audit(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Audit hook best practices — imports, onError handlers, getErrorMessage usage."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.project_root / "apps" / app_name / "src"

    issues: list[dict] = []

    for hook_file in find_hook_files(src_dir):
        try:
            text = hook_file.read_text()
        except OSError:
            continue

        rel = hook_file.name

        # Check: hooks should import from @/types/api (not manual types)
        if "from '@/generated/" in text or 'from "@/generated/' in text:
            issues.append(
                {
                    "file": rel,
                    "check": "import_path",
                    "detail": "Imports directly from @/generated/ — use @/types/api instead",
                }
            )

        # Find all useMutation blocks and check for onError
        mutation_blocks = re.findall(
            r"useMutation\s*\(\s*\{([^}]{0,800})\}",
            text,
            re.DOTALL,
        )
        for block in mutation_blocks:
            if "onError" not in block:
                issues.append(
                    {
                        "file": rel,
                        "check": "missing_onError",
                        "detail": "useMutation missing onError handler",
                    }
                )
            elif "getErrorMessage" not in block:
                issues.append(
                    {
                        "file": rel,
                        "check": "missing_getErrorMessage",
                        "detail": "onError does not use getErrorMessage()",
                    }
                )

    if not issues:
        out.success(f"Hook best practices OK for {app_name}")
        return

    rows = [[i["file"], i["check"], i["detail"]] for i in issues]
    out.table(
        f"Hook Issues ({len(issues)} found in {app_name})",
        [("File", "cyan"), ("Check", "yellow"), ("Detail", "red")],
        rows,
        data_for_json=issues,
    )


@app.command("invalidation-map")
def invalidation_map(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show mutation → invalidation mapping for all hook files."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.project_root / "apps" / app_name / "src"

    entries: list[dict] = []

    for hook_file in find_hook_files(src_dir):
        try:
            text = hook_file.read_text()
        except OSError:
            continue

        rel = hook_file.name

        # Find mutation function definitions
        fn_pattern = re.compile(
            r"export\s+function\s+(use(?:Create|Update|Delete)\w+)",
        )
        # Find invalidateQueries calls with queryKey
        inv_pattern = re.compile(
            r"invalidateQueries\s*\(\s*\{[^}]*queryKey\s*:\s*\[([^\]]+)\]",
        )

        for fn_match in fn_pattern.finditer(text):
            fn_name = fn_match.group(1)
            # Grab region after function definition
            region = text[fn_match.start() : fn_match.start() + 600]
            inv_keys: list[str] = []
            for inv_match in inv_pattern.finditer(region):
                raw = inv_match.group(1).strip()
                parts = [p.strip().strip("\"'") for p in raw.split(",")]
                inv_keys.append(parts[0] if parts else raw)

            entries.append(
                {
                    "file": rel,
                    "mutation": fn_name,
                    "invalidates": ", ".join(inv_keys) if inv_keys else "(none)",
                }
            )

    if not entries:
        out.warn(f"No mutation functions (useCreate*, useUpdate*, useDelete*) found in {app_name}")
        return

    rows = [[e["file"], e["mutation"], e["invalidates"]] for e in entries]
    out.table(
        f"Invalidation Map ({len(entries)} mutations in {app_name})",
        [("File", "cyan"), ("Mutation", "yellow"), ("Invalidates", "green")],
        rows,
        data_for_json=entries,
    )
