"""CI/CD monitoring commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="CI/CD monitoring across kodemeio-* repositories.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Latest workflow run status across ALL repos (pass/fail/running)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 1},
        )
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs:
            run_data = workflow_runs[0]
            conclusion = run_data.get("conclusion") or run_data.get("status", "unknown")
            workflow = run_data.get("name", "")
            created = run_data.get("created_at", "")[:10]
            rows.append([name, workflow, conclusion, created])
        else:
            rows.append([name, "-", "no runs", ""])

    if out.json_mode:
        out.raw_json(
            [
                {
                    "repo": r[0],
                    "workflow": r[1],
                    "conclusion": r[2],
                    "date": r[3],
                }
                for r in rows
            ]
        )
        return

    out.table(
        "CI Status (latest run per repo)",
        [("Repo", "cyan"), ("Workflow", ""), ("Status", "green"), ("Date", "yellow")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of runs")] = 10,
) -> None:
    """Show workflow runs for a specific repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    runs = client.get(
        f"/repos/{client.organization}/{repo}/actions/runs",
        params={"per_page": limit},
    )
    workflow_runs = runs.get("workflow_runs", [])

    if out.json_mode:
        out.raw_json(
            [
                {
                    "id": r["id"],
                    "name": r.get("name", ""),
                    "status": r.get("status"),
                    "conclusion": r.get("conclusion"),
                    "branch": r.get("head_branch"),
                    "created_at": r.get("created_at"),
                    "run_number": r.get("run_number"),
                }
                for r in workflow_runs
            ]
        )
        return

    rows = []
    for r in workflow_runs:
        conclusion = r.get("conclusion") or r.get("status", "unknown")
        rows.append(
            [
                str(r.get("run_number", "")),
                r.get("name", ""),
                r.get("head_branch", ""),
                conclusion,
                r.get("created_at", "")[:10],
            ]
        )

    out.table(
        f"Workflow Runs: {repo}",
        [("Run #", ""), ("Workflow", "cyan"), ("Branch", ""), ("Status", "green"), ("Date", "yellow")],
        rows,
    )


@app.command()
def stats(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Time period (e.g., 7d, 30d)")] = "7d",
) -> None:
    """CI statistics: success rate, avg duration, failure trends."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Parse period
    days = int(period.rstrip("d"))
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0)
    since = since - timedelta(days=days)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = client.get_repos()
    total_runs = 0
    total_success = 0
    total_failure = 0
    repo_stats: list[dict[str, str | int]] = []

    for repo in repos:
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 100, "created": f">={since_str}"},
        )
        workflow_runs = runs.get("workflow_runs", [])
        count = len(workflow_runs)
        success = sum(1 for r in workflow_runs if r.get("conclusion") == "success")
        failure = sum(1 for r in workflow_runs if r.get("conclusion") == "failure")

        total_runs += count
        total_success += success
        total_failure += failure

        if count > 0:
            repo_stats.append(
                {
                    "repo": name,
                    "runs": count,
                    "success": success,
                    "failure": failure,
                    "success_rate": f"{(success / count * 100):.0f}%",
                }
            )

    if out.json_mode:
        out.raw_json(
            {
                "period_days": days,
                "total_runs": total_runs,
                "total_success": total_success,
                "total_failure": total_failure,
                "success_rate": f"{(total_success / total_runs * 100):.0f}%" if total_runs else "N/A",
                "repos": repo_stats,
            }
        )
        return

    # Summary
    rate = f"{(total_success / total_runs * 100):.0f}%" if total_runs else "N/A"
    out.success(f"CI Stats (last {days} days): {total_runs} runs, {rate} success rate")

    rows = [
        [str(s["repo"]), str(s["runs"]), str(s["success"]), str(s["failure"]), str(s["success_rate"])]
        for s in sorted(repo_stats, key=lambda x: int(x["runs"]), reverse=True)
    ]
    out.table(
        "Per-Repo CI Stats",
        [("Repo", "cyan"), ("Runs", ""), ("Pass", "green"), ("Fail", "red"), ("Rate", "yellow")],
        rows,
    )


@app.command()
def rerun(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    workflow: Annotated[str | None, typer.Option("--workflow", "-w", help="Workflow name filter")] = None,
) -> None:
    """Re-trigger the latest failed workflow run."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    runs = client.get(
        f"/repos/{owner}/{repo}/actions/runs",
        params={"status": "failure", "per_page": 5},
    )
    workflow_runs = runs.get("workflow_runs", [])

    if workflow and workflow_runs:
        workflow_runs = [r for r in workflow_runs if workflow.lower() in r.get("name", "").lower()]

    if not workflow_runs:
        out.warn("No failed workflow runs found")
        return

    run_data = workflow_runs[0]
    run_id = run_data["id"]

    # Use gh CLI for rerun (simpler auth)
    gh_run(["run", "rerun", str(run_id), "--repo", f"{owner}/{repo}", "--failed"])
    out.success(f"Re-triggered run #{run_data.get('run_number')} ({run_data.get('name')}) in {repo}")


@app.command("bulk-status")
def bulk_status(ctx: typer.Context) -> None:
    """Table of all repos x workflows with pass/fail matrix."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    all_workflows: set[str] = set()
    repo_workflow_status: dict[str, dict[str, str]] = {}

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 20},
        )
        workflow_runs = runs.get("workflow_runs", [])

        seen: dict[str, str] = {}
        for r in workflow_runs:
            wf_name = r.get("name", "unknown")
            if wf_name not in seen:
                conclusion = r.get("conclusion") or r.get("status", "?")
                seen[wf_name] = conclusion
                all_workflows.add(wf_name)

        repo_workflow_status[name] = seen

    sorted_workflows = sorted(all_workflows)

    if out.json_mode:
        out.raw_json(repo_workflow_status)
        return

    columns: list[tuple[str, str]] = [("Repo", "cyan")]
    columns.extend((wf, "") for wf in sorted_workflows)

    rows = []
    for repo_name in sorted(repo_workflow_status.keys()):
        row = [repo_name]
        for wf in sorted_workflows:
            row.append(repo_workflow_status[repo_name].get(wf, "-"))
        rows.append(row)

    out.table("CI Bulk Status", columns, rows)
