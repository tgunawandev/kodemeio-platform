"""Diff commands - show local vs remote differences."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_op.core.diff import format_diff

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Show differences between local and 1Password.")


@app.callback(invoke_without_command=True)
def diff(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Argument(help="Project name.")] = None,
    environment: Annotated[str | None, typer.Argument(help="Environment name.")] = None,
    show_values: Annotated[bool, typer.Option("--show-values", help="Show actual secret values (careful!).")] = False,
    all_files: Annotated[bool, typer.Option("--all", help="Show diffs for all files.")] = False,
) -> None:
    """Show differences between local .env files and 1Password."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    from kctl_op.core.diff import compute_diff
    from kctl_op.core.op_client import get_item
    from kctl_op.core.parser import parse_env_file

    if all_files:
        files = client.discover_files(
            cfg.scan_roots,
            cfg.exclude_patterns,
            cfg.env_mappings,
            cfg.custom_env_pattern,
        )
        if not files:
            out.warn("No .env files found.")
            return

        has_diffs = False
        json_results = []

        for f in files:
            try:
                local_vars = parse_env_file(f.path)
                try:
                    remote_vars = get_item(f.item_title, cfg.vault)
                except Exception:
                    remote_vars = {}

                if not local_vars and not remote_vars:
                    continue

                diff_result = compute_diff(local_vars, remote_vars)
                if diff_result.has_changes:
                    has_diffs = True
                    out.header(f"{f.item_title}")
                    out.text(format_diff(diff_result, show_values=show_values))
                    json_results.append(
                        {
                            "project": f.project,
                            "environment": f.environment,
                            "added": len(diff_result.added),
                            "removed": len(diff_result.removed),
                            "modified": len(diff_result.modified),
                        }
                    )
            except Exception as e:
                out.warn(f"{f.item_title}: {e}")

        if not has_diffs:
            out.success("All files are in sync.")

        if out.json_mode:
            out.raw_json(json_results)

    elif project and environment:
        files = client.discover_files(
            cfg.scan_roots,
            cfg.exclude_patterns,
            cfg.env_mappings,
            cfg.custom_env_pattern,
        )
        matches = [f for f in files if f.project == project and f.environment == environment]
        if not matches:
            out.error(f"No .env file found for {project}/{environment}")
            raise typer.Exit(code=1)

        f = matches[0]
        local_vars = parse_env_file(f.path)
        try:
            remote_vars = get_item(f.item_title, cfg.vault)
        except Exception:
            remote_vars = {}

        diff_result = compute_diff(local_vars, remote_vars)

        if not diff_result.has_changes:
            out.success(f"{f.item_title}: In sync, no differences.")
        else:
            out.header(f"{f.item_title}")
            out.text(format_diff(diff_result, show_values=show_values))

        if out.json_mode:
            out.raw_json(
                {
                    "project": project,
                    "environment": environment,
                    "added": len(diff_result.added),
                    "removed": len(diff_result.removed),
                    "modified": len(diff_result.modified),
                    "has_changes": diff_result.has_changes,
                }
            )
    else:
        out.error("Specify PROJECT ENVIRONMENT or use --all.")
        raise typer.Exit(code=1)
