"""Environment management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage project environments.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
) -> None:
    """List environments for a project (e.g. production, staging, development)."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        if project:
            proj = c.client.resolve_project(project)
            envs = c.client.project_get(proj, "/environments/")
        else:
            envs = c.client.org_get("/environments/")
        if not isinstance(envs, list):
            envs = []

        rows: list[list[str]] = []
        for env in envs:
            name = env.get("name", "")
            is_hidden = "Yes" if env.get("isHidden", False) else "No"
            rows.append([name, is_hidden])

        target = project or "organization"
        out.table(
            f"Environments — {target}",
            [
                ("Name", "cyan"),
                ("Hidden", "dim"),
            ],
            rows,
            data_for_json=envs,
        )
    except KctlError as e:
        out.error(f"Failed to list environments: {e}")
        raise typer.Exit(1) from e
