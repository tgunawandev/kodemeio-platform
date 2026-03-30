"""Cross-repo pull request management."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="Cross-repo PR management.")


@app.command("list")
def list_prs(ctx: typer.Context) -> None:
    """Open PRs across all kodemeio-* repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    all_prs = []

    for repo in repos:
        name = repo["name"]
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100},
        )
        if isinstance(prs, list):
            for pr in prs:
                all_prs.append(
                    {
                        "repo": name,
                        "number": pr["number"],
                        "title": pr["title"],
                        "author": pr.get("user", {}).get("login", ""),
                        "created_at": pr.get("created_at", ""),
                        "draft": pr.get("draft", False),
                        "labels": [label["name"] for label in pr.get("labels", [])],
                    }
                )

    if out.json_mode:
        out.raw_json(all_prs)
        return

    rows = []
    for pr in sorted(all_prs, key=lambda x: x["created_at"], reverse=True):
        draft_marker = " (draft)" if pr["draft"] else ""
        rows.append(
            [
                pr["repo"],
                f"#{pr['number']}",
                pr["title"][:60] + draft_marker,
                pr["author"],
                pr["created_at"][:10],
            ]
        )

    out.table(
        f"Open Pull Requests ({len(rows)} total)",
        [("Repo", "cyan"), ("#", ""), ("Title", ""), ("Author", "yellow"), ("Created", "")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    number: Annotated[int, typer.Argument(help="PR number")],
) -> None:
    """Show PR details (delegates to gh pr view)."""
    actx: AppContext = ctx.obj
    out = actx.output
    owner = actx.client.organization

    if out.json_mode:
        result = gh_run(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "title,body,state,author,createdAt,mergeable,reviews,labels",
            ]
        )
        out.raw_json(json.loads(result))
        return

    result = gh_run(["pr", "view", str(number), "--repo", f"{owner}/{repo}"])
    out.text(result)


@app.command()
def stale(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Days without activity")] = 14,
) -> None:
    """Find PRs with no activity for N days."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    cutoff = datetime.now(UTC) - timedelta(days=days)
    repos = client.get_repos()
    stale_prs: list[dict[str, str | int]] = []

    for repo in repos:
        name = repo["name"]
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100, "sort": "updated", "direction": "asc"},
        )
        if isinstance(prs, list):
            for pr in prs:
                updated = pr.get("updated_at", "")
                if updated:
                    try:
                        updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        if updated_dt < cutoff:
                            stale_prs.append(
                                {
                                    "repo": name,
                                    "number": pr["number"],
                                    "title": pr["title"],
                                    "author": pr.get("user", {}).get("login", ""),
                                    "updated_at": updated[:10],
                                    "days_stale": (datetime.now(UTC) - updated_dt).days,
                                }
                            )
                    except (ValueError, TypeError):
                        pass

    if out.json_mode:
        out.raw_json(stale_prs)
        return

    rows = [
        [
            str(p["repo"]),
            f"#{p['number']}",
            str(p["title"])[:50],
            str(p["author"]),
            str(p["updated_at"]),
            f"{p['days_stale']}d",
        ]
        for p in sorted(stale_prs, key=lambda x: int(x["days_stale"]), reverse=True)
    ]

    out.table(
        f"Stale PRs (no activity for {days}+ days)",
        [("Repo", "cyan"), ("#", ""), ("Title", ""), ("Author", "yellow"), ("Last Update", ""), ("Stale", "red")],
        rows,
    )
