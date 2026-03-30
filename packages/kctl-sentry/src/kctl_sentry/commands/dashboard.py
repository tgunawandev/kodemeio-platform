"""Dashboard command — quick overview of Sentry state."""

from __future__ import annotations

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Quick overview of Sentry state.")


@app.command("overview")
def overview(ctx: typer.Context) -> None:
    """Show unresolved issues, recent releases, and alert status across projects."""
    c: AppContext = ctx.obj
    out = c.output
    org = c.client.organization

    try:
        # Fetch projects
        projects = c.client.org_get("/projects/")
        if not isinstance(projects, list):
            projects = []

        # Collect unresolved issues per project
        project_rows: list[list[str]] = []
        total_unresolved = 0
        for proj in projects[:20]:  # Cap at 20 projects
            slug = proj.get("slug", "")
            try:
                issues = c.client.project_get(slug, "/issues/", params={"query": "is:unresolved", "limit": 1})
                # Sentry returns X-Hits header, but we can use list length as indicator
                unresolved = proj.get("stats", {}).get("unresolved", len(issues) if isinstance(issues, list) else 0)
            except Exception:
                unresolved = 0
            total_unresolved += unresolved if isinstance(unresolved, int) else 0
            project_rows.append(
                [
                    slug,
                    proj.get("platform", ""),
                    str(unresolved),
                ]
            )

        # Fetch recent releases
        try:
            releases = c.client.org_get("/releases/", params={"per_page": 5})
            if not isinstance(releases, list):
                releases = []
        except Exception:
            releases = []

        release_rows: list[list[str]] = []
        for rel in releases[:5]:
            release_rows.append(
                [
                    rel.get("version", "")[:40],
                    ", ".join(p.get("slug", "") for p in rel.get("projects", [])),
                    (rel.get("dateCreated", "") or "")[:19],
                ]
            )

        # Output
        if project_rows:
            out.table(
                f"Projects — {org} ({total_unresolved} unresolved)",
                [("Project", "cyan"), ("Platform", ""), ("Unresolved", "yellow")],
                project_rows,
                data_for_json={"projects": projects},
            )

        if release_rows:
            out.table(
                "Recent Releases",
                [("Version", "cyan"), ("Projects", ""), ("Created", "dim")],
                release_rows,
                data_for_json={"releases": releases},
            )

        if not project_rows:
            out.info("No projects found")

    except KctlError as e:
        out.error(f"Dashboard failed: {e}")
        raise typer.Exit(1) from e
