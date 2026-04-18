"""Issue/error management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip issues and errors.")


@app.command("list")
def list_(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    project: Annotated[str | None, typer.Option("--project", help="Filter by project slug")] = None,
    status: Annotated[str | None, typer.Option("--status", help="Filter: unresolved, resolved, ignored")] = None,
    sort: Annotated[str, typer.Option("--sort", help="Sort by: last_seen, first_seen, count, priority")] = "-last_seen",
    limit: Annotated[int, typer.Option("--limit", help="Max results")] = 25,
) -> None:
    """List issues."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    params: dict = {"limit": limit, "sort": sort}
    if status:
        params["query"] = f"is:{status}"

    endpoint = f"projects/{org_slug}/{project}/issues/" if project else f"organizations/{org_slug}/issues/"

    issues = c.get_list(endpoint, params=params)

    rows: list[list[str]] = []
    for i in issues:
        issue_id = str(i.get("id", ""))
        title = (i.get("title") or i.get("metadata", {}).get("type", ""))[:60]
        issue_status = i.get("status", "")
        count = str(i.get("count", 0))
        last_seen = str(i.get("lastSeen") or i.get("last_seen") or "")[:19]
        proj = i.get("project", {}).get("slug", "") if isinstance(i.get("project"), dict) else ""

        status_color = {"resolved": "[green]", "ignored": "[yellow]", "unresolved": "[red]"}.get(issue_status, "")
        status_display = f"{status_color}{issue_status}[/]" if status_color else issue_status

        rows.append([issue_id, title, proj, status_display, count, last_seen])

    out.table(
        "Issues",
        [("ID", "cyan"), ("Title", ""), ("Project", "dim"), ("Status", ""), ("Count", ""), ("Last Seen", "dim")],
        rows,
        data_for_json=issues,
    )


@app.command()
def get(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
) -> None:
    """Get issue details with events."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    issue = c.get(f"issues/{issue_id}/")

    metadata = issue.get("metadata", {})
    project = issue.get("project", {})

    sections = [
        (
            "Issue",
            [
                ("ID", str(issue.get("id", ""))),
                ("Title", issue.get("title", "")),
                ("Culprit", issue.get("culprit", "-")),
                ("Status", issue.get("status", "")),
                ("Level", issue.get("level", "")),
                ("Project", project.get("slug", "") if isinstance(project, dict) else str(project)),
                ("Count", str(issue.get("count", 0))),
                ("User Count", str(issue.get("userCount", issue.get("user_count", 0)))),
                ("First Seen", str(issue.get("firstSeen") or issue.get("first_seen") or "")),
                ("Last Seen", str(issue.get("lastSeen") or issue.get("last_seen") or "")),
            ],
        ),
    ]

    if metadata:
        sections.append(("Metadata", [(k, str(v)) for k, v in metadata.items()]))

    # Get latest event
    try:
        latest = c.get(f"issues/{issue_id}/events/latest/")
        if latest:
            sections.append(
                (
                    "Latest Event",
                    [
                        ("Event ID", str(latest.get("eventID") or latest.get("id", ""))),
                        ("Timestamp", str(latest.get("dateCreated") or latest.get("timestamp") or "")),
                        ("Message", str(latest.get("message", ""))[:100]),
                    ],
                )
            )
    except Exception:
        pass

    out.detail("Issue Details", sections, data_for_json=issue)


@app.command()
def resolve(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
) -> None:
    """Mark an issue as resolved."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    c.put(f"issues/{issue_id}/", data={"status": "resolved"})
    out.success(f"Issue {issue_id} marked as resolved")


@app.command()
def ignore(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
) -> None:
    """Mark an issue as ignored."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    c.put(f"issues/{issue_id}/", data={"status": "ignored"})
    out.success(f"Issue {issue_id} marked as ignored")


@app.command()
def delete(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an issue."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    if not force and not typer.confirm(f"Delete issue {issue_id}?"):
        raise typer.Exit(0)

    c.delete(f"issues/{issue_id}/")
    out.success(f"Issue {issue_id} deleted")


@app.command("bulk-resolve")
def bulk_resolve(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    project: Annotated[str, typer.Option("--project", help="Project slug")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Resolve all issues in a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    if not force and not typer.confirm(f"Resolve all issues in {org_slug}/{project}?"):
        raise typer.Exit(0)

    result = c.put(
        f"organizations/{org_slug}/issues/",
        data={"status": "resolved"},
    )
    out.success(f"Bulk resolve completed for {org_slug}/{project}")
    if out.json_mode:
        out.raw_json(result)
