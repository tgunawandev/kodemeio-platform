"""Repository statistics commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Repository statistics across kodemeio-* repos.")


@app.command()
def overview(ctx: typer.Context) -> None:
    """Total repos, total stars, total issues, total PRs."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    total_issues = sum(r.get("open_issues_count", 0) for r in repos)
    total_size = sum(r.get("size", 0) for r in repos)

    if out.json_mode:
        out.raw_json(
            {
                "repos": len(repos),
                "stars": total_stars,
                "forks": total_forks,
                "open_issues": total_issues,
                "total_size_kb": total_size,
            }
        )
        return

    sections = [
        (
            "Overview",
            [
                ("Repositories", str(len(repos))),
                ("Total Stars", str(total_stars)),
                ("Total Forks", str(total_forks)),
                ("Open Issues", str(total_issues)),
                ("Total Size", f"{total_size:,} KB ({total_size // 1024} MB)"),
            ],
        ),
    ]
    out.detail("GitHub Stats Overview", sections)


@app.command()
def activity(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Time period (e.g., 7d, 30d)")] = "30d",
) -> None:
    """Commit activity, PR merge rate, issue velocity."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    days = int(period.rstrip("d"))
    since = datetime.now(UTC) - timedelta(days=days)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        owner = client.organization

        # Commits since period
        try:
            commits = client.get(
                f"/repos/{owner}/{name}/commits",
                params={"since": since_str, "per_page": 100},
            )
            commit_count = len(commits) if isinstance(commits, list) else 0
        except Exception:  # noqa: BLE001
            commit_count = 0

        # Merged PRs in period
        try:
            prs = client.get(
                f"/repos/{owner}/{name}/pulls",
                params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 50},
            )
            merged_count = 0
            if isinstance(prs, list):
                for pr in prs:
                    if pr.get("merged_at"):
                        try:
                            merged_dt = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                            if merged_dt >= since:
                                merged_count += 1
                        except (ValueError, TypeError):
                            pass
        except Exception:  # noqa: BLE001
            merged_count = 0

        if commit_count > 0 or merged_count > 0:
            rows.append([name, str(commit_count), str(merged_count)])

    if out.json_mode:
        out.raw_json(
            [
                {
                    "repo": r[0],
                    "commits": int(r[1]),
                    "merged_prs": int(r[2]),
                }
                for r in rows
            ]
        )
        return

    out.table(
        f"Activity (last {days} days)",
        [("Repo", "cyan"), ("Commits", "green"), ("Merged PRs", "yellow")],
        rows,
    )


@app.command()
def languages(ctx: typer.Context) -> None:
    """Language breakdown across all repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    lang_totals: dict[str, int] = {}

    for repo in repos:
        name = repo["name"]
        try:
            langs = client.get(f"/repos/{client.organization}/{name}/languages")
            if isinstance(langs, dict):
                for lang, bytes_count in langs.items():
                    lang_totals[lang] = lang_totals.get(lang, 0) + bytes_count
        except Exception:  # noqa: BLE001
            pass

    total = sum(lang_totals.values())
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)

    if out.json_mode:
        out.raw_json(
            {
                lang: {"bytes": b, "percentage": f"{(b / total * 100):.1f}%"} if total else {"bytes": b}
                for lang, b in sorted_langs
            }
        )
        return

    rows = []
    for lang, bytes_count in sorted_langs[:20]:
        pct = (bytes_count / total * 100) if total else 0
        bar = "#" * int(pct / 2)
        rows.append([lang, f"{bytes_count:,}", f"{pct:.1f}%", bar])

    out.table(
        "Languages (all repos)",
        [("Language", "cyan"), ("Bytes", ""), ("%", "yellow"), ("Distribution", "green")],
        rows,
    )


@app.command()
def contributors(ctx: typer.Context) -> None:
    """Contributor activity across all repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    contributor_totals: dict[str, int] = {}

    for repo in repos:
        name = repo["name"]
        try:
            contribs = client.get(
                f"/repos/{client.organization}/{name}/contributors",
                params={"per_page": 30},
            )
            if isinstance(contribs, list):
                for c in contribs:
                    login = c.get("login", "unknown")
                    contributor_totals[login] = contributor_totals.get(login, 0) + c.get("contributions", 0)
        except Exception:  # noqa: BLE001
            pass

    sorted_contribs = sorted(contributor_totals.items(), key=lambda x: x[1], reverse=True)

    if out.json_mode:
        out.raw_json([{"login": login, "total_contributions": count} for login, count in sorted_contribs])
        return

    rows = [[login, str(count)] for login, count in sorted_contribs[:20]]
    out.table(
        "Top Contributors (all repos)",
        [("Login", "cyan"), ("Total Contributions", "yellow")],
        rows,
    )
