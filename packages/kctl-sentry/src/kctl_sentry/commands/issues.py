"""Issue management commands — daily error triage."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Error triage — list, inspect, resolve, ignore, assign issues.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    status: Annotated[
        str, typer.Option("--status", "-s", help="Status filter: unresolved, resolved, ignored")
    ] = "unresolved",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 25,
    sort: Annotated[str, typer.Option("--sort", help="Sort by: date, priority, freq, new")] = "date",
) -> None:
    """List recent issues for a project."""
    c: AppContext = ctx.obj
    out = c.output
    proj = c.client.resolve_project(project)

    try:
        query = f"is:{status}"
        issues = c.client.project_get(
            proj,
            "/issues/",
            params={"query": query, "limit": limit, "sort": sort},
        )
        if not isinstance(issues, list):
            issues = []

        rows: list[list[str]] = []
        for iss in issues:
            short_id = iss.get("shortId", "")
            title = (iss.get("title", "") or "")[:60]
            events = str(iss.get("count", 0))
            users = str(iss.get("userCount", 0))
            level = iss.get("level", "")
            last_seen = (iss.get("lastSeen", "") or "")[:19]
            assignee = ""
            if iss.get("assignedTo"):
                assignee = iss["assignedTo"].get("name", "") if isinstance(iss["assignedTo"], dict) else ""

            rows.append([short_id, title, level, events, users, assignee, last_seen])

        out.table(
            f"Issues — {proj} ({status})",
            [
                ("ID", "cyan"),
                ("Title", ""),
                ("Level", "yellow"),
                ("Events", ""),
                ("Users", ""),
                ("Assignee", "dim"),
                ("Last Seen", "dim"),
            ],
            rows,
            data_for_json=issues,
        )
    except KctlError as e:
        out.error(f"Failed to list issues: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID (numeric or short ID)")],
) -> None:
    """Show issue details, stack trace, and affected users."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        issue = c.client.get(f"/issues/{issue_id}/")
        if not isinstance(issue, dict):
            issue = {}

        # Fetch latest event for stack trace
        try:
            latest_event = c.client.get(f"/issues/{issue_id}/events/latest/")
        except Exception:
            latest_event = {}
        if not isinstance(latest_event, dict):
            latest_event = {}

        # Build detail sections
        assignee = ""
        if issue.get("assignedTo") and isinstance(issue["assignedTo"], dict):
            assignee = issue["assignedTo"].get("name", "")

        sections = [
            (
                "Issue",
                [
                    ("ID", issue.get("shortId", str(issue.get("id", "")))),
                    ("Title", issue.get("title", "")),
                    (
                        "Project",
                        issue.get("project", {}).get("slug", "") if isinstance(issue.get("project"), dict) else "",
                    ),
                    ("Level", issue.get("level", "")),
                    ("Status", issue.get("status", "")),
                    ("Assignee", assignee or "[dim]unassigned[/dim]"),
                    ("Events", str(issue.get("count", 0))),
                    ("Users affected", str(issue.get("userCount", 0))),
                    ("First seen", (issue.get("firstSeen", "") or "")[:19]),
                    ("Last seen", (issue.get("lastSeen", "") or "")[:19]),
                ],
            ),
        ]

        # Add stack trace from latest event
        entries = []
        for exc_val in latest_event.get("entries") or []:
            if exc_val.get("type") == "exception":
                for val in exc_val.get("data", {}).get("values") or []:
                    exc_type = val.get("type", "")
                    exc_value = val.get("value", "")
                    frames = (
                        val.get("stacktrace", {}).get("frames", []) if isinstance(val.get("stacktrace"), dict) else []
                    )
                    entries.append((exc_type, exc_value, frames))

        if entries:
            for exc_type, exc_value, frames in entries:
                trace_kvs: list[tuple[str, str]] = [
                    ("Exception", f"{exc_type}: {exc_value}"),
                ]
                # Show last 5 frames
                for frame in frames[-5:]:
                    filename = frame.get("filename", "")
                    lineno = frame.get("lineNo", "")
                    func = frame.get("function", "")
                    trace_kvs.append(("Frame", f"{filename}:{lineno} in {func}"))
                sections.append(("Stack Trace", trace_kvs))

        # Add tags
        tags = issue.get("tags", [])
        if isinstance(tags, list) and tags:
            tag_kvs: list[tuple[str, str]] = []
            for tag in tags[:10]:
                if isinstance(tag, dict):
                    tag_kvs.append((tag.get("key", ""), tag.get("name", "")))
            if tag_kvs:
                sections.append(("Tags", tag_kvs))

        out.detail(
            f"Issue: {issue.get('shortId', issue_id)}",
            sections,
            data_for_json={"issue": issue, "latest_event": latest_event},
        )
    except KctlError as e:
        out.error(f"Failed to show issue: {e}")
        raise typer.Exit(1) from e


@app.command("resolve")
def resolve(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    release: Annotated[str | None, typer.Option("--release", "-r", help="Mark resolved in release")] = None,
) -> None:
    """Resolve an issue. Optionally mark as resolved in a specific release."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict[str, object] = {"status": "resolved"}
        if release:
            payload["statusDetails"] = {"inRelease": release}
        c.client.put(f"/issues/{issue_id}/", json=payload)
        msg = f"Issue {issue_id} resolved"
        if release:
            msg += f" in release {release}"
        out.success(msg)
    except KctlError as e:
        out.error(f"Failed to resolve issue: {e}")
        raise typer.Exit(1) from e


@app.command("ignore")
def ignore(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    duration: Annotated[int | None, typer.Option("--duration", "-d", help="Ignore duration in minutes")] = None,
    count: Annotated[int | None, typer.Option("--count", help="Ignore until N more events")] = None,
) -> None:
    """Ignore an issue, optionally for a duration or until N more events."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict[str, object] = {"status": "ignored"}
        status_details: dict[str, object] = {}
        if duration:
            status_details["ignoreDuration"] = duration
        if count:
            status_details["ignoreCount"] = count
        if status_details:
            payload["statusDetails"] = status_details
        c.client.put(f"/issues/{issue_id}/", json=payload)
        msg = f"Issue {issue_id} ignored"
        if duration:
            msg += f" for {duration} minutes"
        if count:
            msg += f" until {count} more events"
        out.success(msg)
    except KctlError as e:
        out.error(f"Failed to ignore issue: {e}")
        raise typer.Exit(1) from e


@app.command("bulk-resolve")
def bulk_resolve(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug (required)")],
    before: Annotated[
        str | None, typer.Option("--before", help="Resolve issues last seen before date (ISO 8601)")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Bulk-resolve old unresolved issues in a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Fetch unresolved issues
        params: dict[str, object] = {"query": "is:unresolved", "limit": 100}
        if before:
            params["query"] = f"is:unresolved lastSeen:<{before}"

        issues = c.client.project_get(project, "/issues/", params=params)
        if not isinstance(issues, list):
            issues = []

        if not issues:
            out.info("No matching issues to resolve")
            return

        if not force:
            confirm = typer.confirm(f"Resolve {len(issues)} issues in '{project}'?")
            if not confirm:
                out.info("Aborted")
                return

        # Bulk update via issue IDs
        issue_ids = [str(iss.get("id", "")) for iss in issues if iss.get("id")]
        if issue_ids:
            c.client.put(
                f"/projects/{c.client.organization}/{project}/issues/",
                params={"id": issue_ids},
                json={"status": "resolved"},
            )

        out.success(f"Resolved {len(issue_ids)} issues in '{project}'")
    except KctlError as e:
        out.error(f"Bulk resolve failed: {e}")
        raise typer.Exit(1) from e


@app.command("assign")
def assign(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    to: Annotated[str, typer.Option("--to", help="User email or 'me'")],
) -> None:
    """Assign an issue to a team member."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        c.client.put(f"/issues/{issue_id}/", json={"assignedTo": to})
        out.success(f"Issue {issue_id} assigned to {to}")
    except KctlError as e:
        out.error(f"Failed to assign issue: {e}")
        raise typer.Exit(1) from e
