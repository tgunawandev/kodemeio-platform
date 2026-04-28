"""Issue management commands — daily use."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import (
    COMMENT_CREATE_MUTATION,
    ISSUE_CREATE_MUTATION,
    ISSUE_SEARCH_QUERY,
    ISSUE_SHOW_QUERY,
    ISSUE_UPDATE_MUTATION,
    ISSUES_LIST_QUERY,
    TEAM_BY_KEY_QUERY,
    USER_BY_NAME_QUERY,
    WORKFLOW_STATE_QUERY,
)

app = typer.Typer(help="Issue management.")


def _resolve_team_id(ctx: AppContext, team_key: str) -> str:
    """Resolve a team key (e.g., 'KOD') to its UUID."""
    data = ctx.client.query(TEAM_BY_KEY_QUERY, {"key": team_key})
    nodes = data.get("teams", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"Team '{team_key}' not found")
    return nodes[0]["id"]


def _resolve_user_id(ctx: AppContext, name: str) -> str:
    """Resolve a user display name to their UUID."""
    data = ctx.client.query(USER_BY_NAME_QUERY, {"name": name})
    nodes = data.get("users", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"User '{name}' not found")
    return nodes[0]["id"]


def _resolve_state_id(ctx: AppContext, team_key: str, state_name: str) -> str:
    """Resolve a workflow state name to its UUID."""
    data = ctx.client.query(WORKFLOW_STATE_QUERY, {"teamKey": team_key, "stateName": state_name})
    nodes = data.get("workflowStates", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"State '{state_name}' not found for team '{team_key}'")
    return nodes[0]["id"]


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key (e.g., KOD)")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state name")] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="Filter by assignee ('me' for self)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """List issues with optional filters."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    team_key = team or actx.default_team
    variables: dict[str, str | int | None] = {"first": limit}

    if team_key:
        variables["teamKey"] = team_key
    if state:
        variables["state"] = state

    # Resolve 'me' to viewer ID
    if assignee == "me":
        viewer = client.viewer()
        variables["assigneeId"] = viewer["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    data = client.query(ISSUES_LIST_QUERY, variables)
    issues = data.get("issues", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(issues)
        return

    if not issues:
        out.info("No issues found")
        return

    rows = [
        [
            issue.get("identifier", ""),
            issue.get("title", "")[:55],
            str(issue.get("priority", "-")),
            issue.get("state", {}).get("name", ""),
            (issue.get("assignee") or {}).get("name", "unassigned"),
        ]
        for issue in issues
    ]
    out.table(
        f"Issues ({len(issues)})",
        [("ID", "cyan"), ("Title", "white"), ("P", "yellow"), ("State", "green"), ("Assignee", "magenta")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID (UUID or identifier like KOD-123)")],
) -> None:
    """Show issue details, comments, and history."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(ISSUE_SHOW_QUERY, {"id": issue_id})
    issue = data.get("issue", {})

    if out.json_mode:
        out.raw_json(issue)
        return

    labels = [label["name"] for label in issue.get("labels", {}).get("nodes", [])]
    sections = [
        (
            "Issue",
            [
                ("Identifier", issue.get("identifier", "")),
                ("Title", issue.get("title", "")),
                ("State", issue.get("state", {}).get("name", "")),
                ("Priority", issue.get("priorityLabel", "")),
                ("Estimate", str(issue.get("estimate") or "-")),
                ("Assignee", (issue.get("assignee") or {}).get("name", "unassigned")),
                ("Team", (issue.get("team") or {}).get("name", "")),
                ("Project", (issue.get("project") or {}).get("name", "-")),
                ("Cycle", (issue.get("cycle") or {}).get("name", "-")),
                ("Labels", ", ".join(labels) if labels else "-"),
                ("URL", issue.get("url", "")),
            ],
        ),
    ]

    if issue.get("description"):
        sections.append(("Description", [("", issue["description"][:500])]))

    comments = issue.get("comments", {}).get("nodes", [])
    if comments:
        comment_rows = [
            (f"{c.get('user', {}).get('name', '?')} ({c.get('createdAt', '')[:10]})", c.get("body", "")[:200])
            for c in comments[:10]
        ]
        sections.append(("Comments", comment_rows))

    out.detail(issue.get("identifier", "Issue"), sections)


@app.command()
def create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="Issue title")],
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Issue description")] = None,
    priority: Annotated[
        int | None, typer.Option("--priority", "-p", help="Priority 0-4 (0=none, 1=urgent, 4=low)")
    ] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="Assignee name ('me' for self)")] = None,
) -> None:
    """Create a new issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    if not team_key:
        out.error("Team key required. Use --team or set default_team in config.")
        raise typer.Exit(1)

    team_id = _resolve_team_id(actx, team_key)
    variables: dict[str, str | int | None] = {"teamId": team_id, "title": title}

    if description:
        variables["description"] = description
    if priority is not None:
        variables["priority"] = priority
    if assignee == "me":
        variables["assigneeId"] = actx.client.viewer()["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    data = actx.client.query(ISSUE_CREATE_MUTATION, variables)
    result = data.get("issueCreate", {})
    issue = result.get("issue", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Created {issue.get('identifier', '?')}: {issue.get('title', '')}")
    out.kv("URL", issue.get("url", ""))


@app.command()
def update(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    state: Annotated[str | None, typer.Option("--state", "-s", help="New state name")] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="New assignee")] = None,
    priority: Annotated[int | None, typer.Option("--priority", "-p", help="New priority (0-4)")] = None,
    title: Annotated[str | None, typer.Option("--title", help="New title")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="New description")] = None,
) -> None:
    """Update an existing issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    variables: dict[str, str | int | None] = {"id": issue_id}

    if state:
        team_key = actx.default_team
        if not team_key:
            out.error("default_team must be configured to resolve state names")
            raise typer.Exit(1)
        variables["stateId"] = _resolve_state_id(actx, team_key, state)

    if assignee == "me":
        variables["assigneeId"] = actx.client.viewer()["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    if priority is not None:
        variables["priority"] = priority
    if title:
        variables["title"] = title
    if description:
        variables["description"] = description

    data = actx.client.query(ISSUE_UPDATE_MUTATION, variables)
    result = data.get("issueUpdate", {})
    issue = result.get("issue", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Updated {issue.get('identifier', '?')}: {issue.get('title', '')}")


@app.command()
def comment(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    body: Annotated[str, typer.Option("--body", "-b", help="Comment text")],
) -> None:
    """Add a comment to an issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(COMMENT_CREATE_MUTATION, {"issueId": issue_id, "body": body})
    result = data.get("commentCreate", {})

    if out.json_mode:
        out.raw_json(result)
        return

    if result.get("success"):
        out.success("Comment added")
    else:
        out.error("Failed to add comment")


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """Full-text search for issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(ISSUE_SEARCH_QUERY, {"term": query, "first": limit})
    issues = data.get("searchIssues", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(issues)
        return

    if not issues:
        out.info(f"No issues matching '{query}'")
        return

    rows = [
        [
            issue.get("identifier", ""),
            issue.get("title", "")[:55],
            issue.get("state", {}).get("name", ""),
            (issue.get("assignee") or {}).get("name", ""),
        ]
        for issue in issues
    ]
    out.table(
        f"Search: '{query}' ({len(issues)} results)",
        [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta")],
        rows,
    )
