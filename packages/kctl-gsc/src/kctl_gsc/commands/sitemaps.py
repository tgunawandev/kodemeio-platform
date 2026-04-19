"""sitemaps — list / submit / status / delete."""

from __future__ import annotations

import typer

app = typer.Typer(help="Sitemap management.")


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List sitemaps submitted for the active property."""
    actx = ctx.obj
    data = actx.client.sitemaps().list(siteUrl=actx.property).execute() or {}
    entries = data.get("sitemap", [])
    data_for_json = [
        {
            "path": s.get("path", ""),
            "last_submitted": s.get("lastSubmitted", ""),
            "pending": bool(s.get("isPending", False)),
            "is_index": bool(s.get("isSitemapsIndex", False)),
        }
        for s in entries
    ]
    rows = [
        [
            str(d["path"]),
            str(d["last_submitted"]),
            str(d["pending"]),
            str(d["is_index"]),
        ]
        for d in data_for_json
    ]
    actx.output.table(
        "Sitemaps",
        [("path", "cyan"), ("last_submitted", ""), ("pending", ""), ("is_index", "")],
        rows,
        data_for_json=data_for_json,
    )


@app.command()
def submit(ctx: typer.Context, url: str) -> None:
    """Submit a sitemap URL."""
    actx = ctx.obj
    actx.client.sitemaps().submit(siteUrl=actx.property, feedpath=url).execute()
    actx.output.success(f"Submitted {url}")


@app.command()
def status(ctx: typer.Context, url: str) -> None:
    """Fetch detailed status for a submitted sitemap."""
    actx = ctx.obj
    data = actx.client.sitemaps().get(siteUrl=actx.property, feedpath=url).execute() or {}
    sections = [
        (
            "Sitemap",
            [
                ("path", str(data.get("path", ""))),
                ("type", str(data.get("type", ""))),
                ("last_submitted", str(data.get("lastSubmitted", ""))),
                ("last_downloaded", str(data.get("lastDownloaded", ""))),
                ("pending", str(bool(data.get("isPending", False)))),
                ("is_index", str(bool(data.get("isSitemapsIndex", False)))),
                ("warnings", str(data.get("warnings", ""))),
                ("errors", str(data.get("errors", ""))),
            ],
        )
    ]
    actx.output.detail(f"Sitemap: {url}", sections, data_for_json=data)


@app.command()
def delete(ctx: typer.Context, url: str) -> None:
    """Remove a sitemap submission."""
    actx = ctx.obj
    actx.client.sitemaps().delete(siteUrl=actx.property, feedpath=url).execute()
    actx.output.success(f"Deleted {url}")
