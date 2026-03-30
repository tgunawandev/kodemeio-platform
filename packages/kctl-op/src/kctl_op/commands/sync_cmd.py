"""Push and pull sync commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_op.core.callbacks import AppContext

push_app = typer.Typer(help="Push .env files to 1Password.")
pull_app = typer.Typer(help="Pull .env files from 1Password.")


def _find_file(actx: AppContext, project: str, environment: str):
    """Find a specific EnvFile by project and environment."""
    cfg = actx.service_config
    files = actx.client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )
    matches = [f for f in files if f.project == project and f.environment == environment]
    if not matches:
        actx.output.error(f"No .env file found for {project}/{environment}")
        raise typer.Exit(code=1)
    return matches[0]


def _show_results(out, results: list, action: str) -> None:
    """Display push/pull results as a table."""
    rows = []
    json_data = []
    ok_count = 0
    fail_count = 0

    for env_file, success, message in results:
        status = "[green]\u2713[/green]" if success else "[red]\u2717[/red]"
        if success:
            ok_count += 1
        else:
            fail_count += 1
        rows.append([env_file.project, env_file.environment, status, message])
        json_data.append(
            {
                "project": env_file.project,
                "environment": env_file.environment,
                "success": success,
                "message": message,
            }
        )

    out.table(
        title=f"{action} Results",
        columns=[
            ("Project", "green"),
            ("Environment", "cyan"),
            ("Status", ""),
            ("Message", ""),
        ],
        rows=rows,
        data_for_json=json_data,
    )

    total = ok_count + fail_count
    out.text(f"\n{action}ed {ok_count}/{total} files")


@push_app.callback(invoke_without_command=True)
def push(
    ctx: typer.Context,
    all_files: Annotated[bool, typer.Option("--all", help="Push all discovered .env files.")] = False,
    project: Annotated[str | None, typer.Option("-p", "--project", help="Target project name.")] = None,
    environment: Annotated[str | None, typer.Option("-e", "--env", help="Target environment.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without changes.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
) -> None:
    """Push .env files to 1Password vault."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    if dry_run:
        out.info("[DRY RUN] No changes will be made.")

    if all_files:
        results = client.push_all(
            cfg.scan_roots,
            cfg.exclude_patterns,
            cfg.env_mappings,
            cfg.custom_env_pattern,
            dry_run=dry_run,
            force=force,
        )
        _show_results(out, results, "Push")
    elif project and environment:
        env_file = _find_file(actx, project, environment)
        ok, msg, diff = client.push_file(env_file, dry_run=dry_run, force=force)
        status = "[green]\u2713[/green]" if ok else "[red]\u2717[/red]"
        out.text(f"{status} {env_file.item_title}: {msg}")
    else:
        out.error("Specify --all or both -p PROJECT and -e ENV.")
        raise typer.Exit(code=1)


@pull_app.callback(invoke_without_command=True)
def pull(
    ctx: typer.Context,
    all_files: Annotated[bool, typer.Option("--all", help="Pull all discovered .env files.")] = False,
    project: Annotated[str | None, typer.Option("-p", "--project", help="Target project name.")] = None,
    environment: Annotated[str | None, typer.Option("-e", "--env", help="Target environment.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without changes.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation.")] = False,
    no_backup: Annotated[bool, typer.Option("--no-backup", help="Skip creating backup before overwriting.")] = False,
) -> None:
    """Pull .env files from 1Password vault."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    if dry_run:
        out.info("[DRY RUN] No changes will be made.")

    backup = not no_backup

    if all_files:
        results = client.pull_all(
            cfg.scan_roots,
            cfg.exclude_patterns,
            cfg.env_mappings,
            cfg.custom_env_pattern,
            dry_run=dry_run,
            force=force,
            backup=backup,
        )
        _show_results(out, results, "Pull")
    elif project and environment:
        env_file = _find_file(actx, project, environment)
        ok, msg, diff = client.pull_file(env_file, dry_run=dry_run, force=force, backup=backup)
        status = "[green]\u2713[/green]" if ok else "[red]\u2717[/red]"
        out.text(f"{status} {env_file.item_title}: {msg}")
    else:
        out.error("Specify --all or both -p PROJECT and -e ENV.")
        raise typer.Exit(code=1)
