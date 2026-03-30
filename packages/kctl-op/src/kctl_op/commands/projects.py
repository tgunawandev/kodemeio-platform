"""Project management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Project discovery and status.")


@app.command(name="list")
def list_projects(ctx: typer.Context) -> None:
    """List all projects found across scan roots."""
    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )

    # Group by project
    projects: dict[str, list] = {}
    for f in files:
        projects.setdefault(f.project, []).append(f)

    if not projects:
        out.warn("No projects found.")
        return

    rows = []
    json_data = []
    for project_name in sorted(projects.keys()):
        envs = projects[project_name]
        env_names = ", ".join(sorted(set(f.environment for f in envs)))
        scan_root = str(envs[0].scan_root) if envs else ""

        rows.append([project_name, str(len(envs)), env_names, scan_root])
        json_data.append(
            {
                "project": project_name,
                "env_count": len(envs),
                "environments": sorted(set(f.environment for f in envs)),
                "scan_root": scan_root,
            }
        )

    out.table(
        title=f"Projects ({len(projects)})",
        columns=[
            ("Project", "green"),
            ("Files", "cyan"),
            ("Environments", ""),
            ("Scan Root", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


@app.command()
def status(
    ctx: typer.Context,
    project: Annotated[str, typer.Argument(help="Project name.")],
) -> None:
    """Show sync status for all environments in a project."""
    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )
    project_files = [f for f in files if f.project == project]

    if not project_files:
        out.error(f"Project '{project}' not found.")
        raise typer.Exit(code=1)

    rows = []
    json_data = []
    for f in project_files:
        try:
            st = client.file_status(f)
            local_vars = st.get("local_vars", 0)
            remote_vars = st.get("remote_vars", 0)

            if st.get("in_sync"):
                status_str = "[green]\u2713 In sync[/green]"
            elif not st.get("remote_exists"):
                status_str = "[yellow]\u2191 Push needed[/yellow]"
            elif not st.get("local_exists"):
                status_str = "[yellow]\u2193 Pull needed[/yellow]"
            else:
                status_str = "[red]\u2260 Out of sync[/red]"

            rows.append(
                [
                    f.environment,
                    str(local_vars),
                    str(remote_vars),
                    status_str,
                    str(f.path),
                ]
            )
            json_data.append(
                {
                    "environment": f.environment,
                    "local_vars": local_vars,
                    "remote_vars": remote_vars,
                    "in_sync": st.get("in_sync"),
                    "path": str(f.path),
                }
            )
        except Exception as e:
            rows.append([f.environment, "?", "?", "[red]Error[/red]", str(e)])
            json_data.append({"environment": f.environment, "error": str(e)})

    out.table(
        title=f"Project: {project}",
        columns=[
            ("Environment", "cyan"),
            ("Local Vars", ""),
            ("Remote Vars", ""),
            ("Status", ""),
            ("Path", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


@app.command()
def envs(
    ctx: typer.Context,
    project: Annotated[str, typer.Argument(help="Project name.")],
) -> None:
    """List all .env files for a project."""
    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )
    project_files = [f for f in files if f.project == project]

    if not project_files:
        out.error(f"Project '{project}' not found.")
        raise typer.Exit(code=1)

    rows = []
    json_data = []
    for f in project_files:
        rows.append(
            [
                f.environment,
                f.item_title,
                str(f.path),
                str(f.scan_root),
            ]
        )
        json_data.append(
            {
                "environment": f.environment,
                "item_title": f.item_title,
                "path": str(f.path),
                "scan_root": str(f.scan_root),
            }
        )

    out.table(
        title=f"Environments for {project}",
        columns=[
            ("Environment", "cyan"),
            ("1Password Item", "yellow"),
            ("Path", ""),
            ("Scan Root", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )
