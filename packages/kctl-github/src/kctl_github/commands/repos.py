"""Cross-repo overview commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Cross-repo overview for kodemeio-* repositories.")


@app.command("list")
def list_repos(ctx: typer.Context) -> None:
    """List all kodemeio-* repos with visibility, default branch, last push."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()

    if out.json_mode:
        out.raw_json(
            [
                {
                    "name": r["name"],
                    "visibility": "private" if r.get("private") else "public",
                    "default_branch": r.get("default_branch", "main"),
                    "pushed_at": r.get("pushed_at", ""),
                    "description": r.get("description", ""),
                }
                for r in repos
            ]
        )
        return

    rows = []
    for r in sorted(repos, key=lambda x: x["name"]):
        rows.append(
            [
                r["name"],
                "private" if r.get("private") else "public",
                r.get("default_branch", "main"),
                _format_date(r.get("pushed_at", "")),
            ]
        )

    out.table(
        f"Repositories ({len(rows)} matching '{client.repo_prefix}*')",
        [("Name", "cyan"), ("Visibility", ""), ("Branch", ""), ("Last Push", "yellow")],
        rows,
    )


@app.command()
def status(ctx: typer.Context) -> None:
    """Aggregated status: open PRs, failing CI, stale branches per repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        owner = client.organization

        # Open PRs count
        prs = client.get(f"/repos/{owner}/{name}/pulls", params={"state": "open", "per_page": 100})
        pr_count = len(prs) if isinstance(prs, list) else 0

        # Latest CI status
        runs = client.get(f"/repos/{owner}/{name}/actions/runs", params={"per_page": 1})
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs:
            ci_status = workflow_runs[0].get("conclusion") or workflow_runs[0].get("status", "unknown")
        else:
            ci_status = "none"

        # Branch count
        branches = client.get(f"/repos/{owner}/{name}/branches", params={"per_page": 100})
        branch_count = len(branches) if isinstance(branches, list) else 0

        rows.append([name, str(pr_count), ci_status, str(branch_count)])

    if out.json_mode:
        out.raw_json(
            [
                {
                    "repo": r[0],
                    "open_prs": int(r[1]),
                    "ci_status": r[2],
                    "branches": int(r[3]),
                }
                for r in rows
            ]
        )
        return

    out.table(
        "Repository Status",
        [("Repo", "cyan"), ("Open PRs", "yellow"), ("CI", "green"), ("Branches", "")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Repository name (e.g., kodemeio-next)")],
) -> None:
    """Show single repo details (size, languages, contributors)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repo = client.get_repo(name)
    languages = client.get(f"/repos/{owner}/{name}/languages")
    contributors = client.get(f"/repos/{owner}/{name}/contributors", params={"per_page": 10})

    if out.json_mode:
        out.raw_json(
            {
                "name": repo["name"],
                "description": repo.get("description", ""),
                "size_kb": repo.get("size", 0),
                "default_branch": repo.get("default_branch"),
                "languages": languages,
                "top_contributors": [
                    {"login": c["login"], "contributions": c["contributions"]}
                    for c in (contributors if isinstance(contributors, list) else [])[:5]
                ],
            }
        )
        return

    total_bytes = sum(languages.values()) if isinstance(languages, dict) else 0
    lang_lines = []
    if isinstance(languages, dict):
        for lang, bytes_count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = (bytes_count / total_bytes * 100) if total_bytes else 0
            lang_lines.append((lang, f"{pct:.1f}%"))

    contrib_lines = []
    if isinstance(contributors, list):
        for c in contributors[:5]:
            contrib_lines.append((c["login"], f"{c['contributions']} commits"))

    sections = [
        (
            "Repository",
            [
                ("Name", repo["name"]),
                ("Description", repo.get("description") or "(none)"),
                ("Visibility", "private" if repo.get("private") else "public"),
                ("Default Branch", repo.get("default_branch", "main")),
                ("Size", f"{repo.get('size', 0)} KB"),
                ("Open Issues", str(repo.get("open_issues_count", 0))),
                ("Created", _format_date(repo.get("created_at", ""))),
                ("Last Push", _format_date(repo.get("pushed_at", ""))),
            ],
        ),
        ("Languages (top 5)", lang_lines),
        ("Contributors (top 5)", contrib_lines),
    ]
    out.detail(f"Repository: {name}", sections)


def _format_date(iso_date: str) -> str:
    """Format an ISO date string to a shorter readable format."""
    if not iso_date:
        return ""
    try:
        return iso_date[:10]
    except Exception:
        return iso_date
