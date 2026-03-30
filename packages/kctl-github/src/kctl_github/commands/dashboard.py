"""Dashboard -- quick overview command."""

from __future__ import annotations

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Quick overview dashboard.")


@app.callback(invoke_without_command=True)
def dashboard(ctx: typer.Context) -> None:
    """Show repos count, open PRs, failing CI, rate limits summary."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Get repos
    repos = client.get_repos()
    repo_count = len(repos)

    # Count open PRs across repos
    total_open_prs = 0
    failing_ci = 0
    for repo in repos:
        name = repo["name"]
        # Get open PRs
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100},
        )
        if isinstance(prs, list):
            total_open_prs += len(prs)

        # Get latest workflow run
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 1},
        )
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs and workflow_runs[0].get("conclusion") == "failure":
            failing_ci += 1

    # Rate limits
    rate = client.get("/rate_limit")
    core = rate.get("resources", {}).get("core", {})

    if out.json_mode:
        out.raw_json(
            {
                "repos": repo_count,
                "open_prs": total_open_prs,
                "failing_ci": failing_ci,
                "rate_limit_remaining": core.get("remaining"),
            }
        )
        return

    sections = [
        (
            "Repositories",
            [
                ("Total kodemeio-* repos", str(repo_count)),
            ],
        ),
        (
            "Pull Requests",
            [
                ("Open PRs (all repos)", str(total_open_prs)),
            ],
        ),
        (
            "CI/CD",
            [
                ("Repos with failing CI", str(failing_ci)),
            ],
        ),
        (
            "API",
            [
                ("Rate limit remaining", f"{core.get('remaining', '?')}/{core.get('limit', '?')}"),
            ],
        ),
    ]
    out.detail("GitHub Dashboard", sections)
