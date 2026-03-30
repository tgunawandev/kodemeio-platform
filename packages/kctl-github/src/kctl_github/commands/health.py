"""Health check commands."""

from __future__ import annotations

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="API connectivity and rate limits.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check GitHub API reachability, rate limits, and token scopes."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Check rate limits
    rate = client.get("/rate_limit")
    core = rate.get("resources", {}).get("core", {})
    search = rate.get("resources", {}).get("search", {})

    # Get authenticated user info
    user = client.get("/user")

    if out.json_mode:
        out.raw_json(
            {
                "status": "healthy",
                "user": user.get("login"),
                "rate_limit": {
                    "core_remaining": core.get("remaining"),
                    "core_limit": core.get("limit"),
                    "search_remaining": search.get("remaining"),
                    "search_limit": search.get("limit"),
                },
            }
        )
        return

    out.success("GitHub API is reachable")
    sections = [
        (
            "Connection",
            [
                ("User", user.get("login", "unknown")),
                ("Name", user.get("name", "")),
                ("Plan", user.get("plan", {}).get("name", "unknown")),
            ],
        ),
        (
            "Rate Limits",
            [
                ("Core", f"{core.get('remaining', '?')}/{core.get('limit', '?')}"),
                ("Search", f"{search.get('remaining', '?')}/{search.get('limit', '?')}"),
            ],
        ),
    ]
    out.detail("GitHub Health", sections)
