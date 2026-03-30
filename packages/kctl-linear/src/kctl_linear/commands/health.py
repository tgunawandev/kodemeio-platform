"""Health check — verify API connectivity."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext

app = typer.Typer(help="API health check.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check Linear API connectivity and show current user info."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    viewer = client.viewer()

    if out.json_mode:
        out.raw_json({"status": "ok", "viewer": viewer})
        return

    sections = [
        ("API Status", [("Status", "Connected"), ("Endpoint", "https://api.linear.app/graphql")]),
        (
            "Authenticated User",
            [
                ("Name", viewer.get("name", "")),
                ("Email", viewer.get("email", "")),
                ("Admin", str(viewer.get("admin", False))),
                ("Active", str(viewer.get("active", True))),
            ],
        ),
    ]
    out.detail("Linear Health", sections)
