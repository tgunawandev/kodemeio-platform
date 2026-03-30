"""Release tracking commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage releases and deploy tracking.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project slug")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """List recent releases."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        params: dict[str, object] = {"per_page": limit}
        if project:
            params["project"] = c.client.resolve_project(project)

        releases = c.client.org_get("/releases/", params=params)
        if not isinstance(releases, list):
            releases = []

        rows: list[list[str]] = []
        for rel in releases:
            version = (rel.get("version", "") or "")[:50]
            projects = ", ".join(p.get("slug", "") for p in rel.get("projects", []) if isinstance(p, dict))
            new_groups = str(rel.get("newGroups", 0))
            created = (rel.get("dateCreated", "") or "")[:19]
            deploy_count = str(rel.get("deployCount", 0))
            rows.append([version, projects, new_groups, deploy_count, created])

        out.table(
            "Releases",
            [
                ("Version", "cyan"),
                ("Projects", ""),
                ("New Issues", "yellow"),
                ("Deploys", ""),
                ("Created", "dim"),
            ],
            rows,
            data_for_json=releases,
        )
    except KctlError as e:
        out.error(f"Failed to list releases: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version (e.g. 1.2.3 or git SHA)")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
) -> None:
    """Create a new release for a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload = {
            "version": version,
            "projects": [project],
        }
        result = c.client.org_post("/releases/", json=payload)
        if not isinstance(result, dict):
            result = {}

        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Release created: {version}")
            out.kv("Version", result.get("version", ""))
            projs = ", ".join(p.get("slug", "") for p in result.get("projects", []) if isinstance(p, dict))
            out.kv("Projects", projs)
    except KctlError as e:
        out.error(f"Failed to create release: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version")],
) -> None:
    """Show release details and associated issues."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        release = c.client.org_get(f"/releases/{version}/")
        if not isinstance(release, dict):
            release = {}

        projects = ", ".join(p.get("slug", "") for p in release.get("projects", []) if isinstance(p, dict))

        # Fetch associated issues (new in this release)
        try:
            issues = c.client.org_get(
                f"/releases/{version}/resolved/",
            )
            if not isinstance(issues, list):
                issues = []
        except Exception:
            issues = []

        sections = [
            (
                "Release",
                [
                    ("Version", release.get("version", "")),
                    ("Projects", projects),
                    ("New issues", str(release.get("newGroups", 0))),
                    ("Deploy count", str(release.get("deployCount", 0))),
                    ("Created", (release.get("dateCreated", "") or "")[:19]),
                    ("First event", (release.get("firstEvent", "") or "N/A")[:19]),
                    ("Last event", (release.get("lastEvent", "") or "N/A")[:19]),
                ],
            ),
        ]

        # Commit info
        last_commit = release.get("lastCommit")
        if isinstance(last_commit, dict):
            sections.append(
                (
                    "Last Commit",
                    [
                        ("SHA", (last_commit.get("id", "") or "")[:12]),
                        ("Message", (last_commit.get("message", "") or "")[:80]),
                        (
                            "Author",
                            last_commit.get("author", {}).get("name", "")
                            if isinstance(last_commit.get("author"), dict)
                            else "",
                        ),
                    ],
                )
            )

        # Resolved issues in this release
        if issues:
            issue_kvs: list[tuple[str, str]] = []
            for iss in issues[:10]:
                if isinstance(iss, dict):
                    issue_kvs.append(
                        (
                            iss.get("shortId", str(iss.get("id", ""))),
                            (iss.get("title", "") or "")[:60],
                        )
                    )
            if issue_kvs:
                sections.append(("Resolved Issues", issue_kvs))

        out.detail(
            f"Release: {version}",
            sections,
            data_for_json={"release": release, "resolved_issues": issues},
        )
    except KctlError as e:
        out.error(f"Failed to show release: {e}")
        raise typer.Exit(1) from e


@app.command("associate")
def associate_commits(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version")],
    commits: Annotated[str, typer.Option("--commits", help="Commit range: repo@from..to")],
) -> None:
    """Associate commits with a release for tracking regressions."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Parse "repo@from..to" format
        if "@" in commits and ".." in commits:
            repo_part, range_part = commits.split("@", 1)
            commit_from, commit_to = range_part.split("..", 1)
            commit_list = [
                {
                    "repository": repo_part,
                    "previousCommit": commit_from,
                    "currentCommit": commit_to,
                }
            ]
        else:
            # Treat as simple commit SHA
            commit_list = [{"id": commits}]

        payload = {
            "commits": commit_list,
        }
        c.client.org_put(f"/releases/{version}/", json=payload)
        out.success(f"Commits associated with release {version}")
    except KctlError as e:
        out.error(f"Failed to associate commits: {e}")
        raise typer.Exit(1) from e
