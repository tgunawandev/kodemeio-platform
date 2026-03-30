"""Health check commands."""

from __future__ import annotations

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.config import resolve_active_profile_name
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="API connectivity checks.")


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Check Sentry API connectivity, org info, and rate limits."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)

    try:
        result = c.client.check_health()
        org_name = result.get("name", "unknown")
        org_slug = result.get("slug", "unknown")
        plan = result.get("plan", {}).get("name", "unknown") if isinstance(result.get("plan"), dict) else "unknown"

        # Get project count
        try:
            projects = c.client.org_get("/projects/")
            project_count = len(projects) if isinstance(projects, list) else 0
        except Exception:
            project_count = 0

        sections = [
            (
                "Health",
                [
                    ("Status", "[green]Connected[/green]"),
                    ("Profile", active),
                    ("Organization", f"{org_name} ({org_slug})"),
                    ("Plan", plan),
                    ("Projects", str(project_count)),
                ],
            )
        ]
        out.detail(
            "Sentry Health",
            sections,
            data_for_json={
                "healthy": True,
                "profile": active,
                "organization": org_slug,
                "org_name": org_name,
                "plan": plan,
                "project_count": project_count,
            },
        )
    except KctlError as e:
        out.detail(
            "Sentry Health",
            [
                (
                    "Health",
                    [
                        ("Status", "[red]Unreachable[/red]"),
                        ("Error", str(e)),
                    ],
                )
            ],
            data_for_json={"healthy": False, "error": str(e)},
        )
        raise typer.Exit(1) from e
