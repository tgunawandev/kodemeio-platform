"""Share link management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Share link management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List all share links."""
    c: AppContext = ctx.obj
    result = c.client.post("shares.list", data={"offset": offset, "limit": limit})
    shares = result.get("data", [])

    rows = [
        [
            s.get("id", "")[:8],
            s.get("documentTitle", "") or s.get("documentId", "")[:8],
            str(s.get("includeChildDocuments", False)),
            "yes" if s.get("published") else "no",
            s.get("url", "")[:50] if s.get("url") else "-",
            (s.get("createdAt") or "")[:10],
        ]
        for s in shares
    ]

    c.output.table(
        f"Shares ({len(shares)})",
        [
            ("ID", "cyan"),
            ("Document", "green"),
            ("Children", ""),
            ("Published", ""),
            ("URL", "dim"),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=shares,
    )


@app.command()
def create(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID to share")],
    include_children: Annotated[bool, typer.Option("--children", help="Include child documents")] = False,
) -> None:
    """Create a share link for a document."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "shares.create",
        data={
            "documentId": document_id,
            "includeChildDocuments": include_children,
        },
    )
    share = result.get("data", {})

    c.output.detail(
        "Share Created",
        [
            (
                "Details",
                [
                    ("ID", share.get("id", "")),
                    ("Document", share.get("documentId", "")),
                    ("URL", share.get("url", "")),
                    ("Children", str(share.get("includeChildDocuments", False))),
                ],
            )
        ],
        data_for_json=share,
    )


@app.command()
def revoke(
    ctx: typer.Context,
    share_id: Annotated[str, typer.Argument(help="Share ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Revoke a share link."""
    c: AppContext = ctx.obj

    if not force and not typer.confirm(f"Revoke share {share_id}?"):
        raise typer.Abort()

    c.client.post("shares.revoke", data={"id": share_id})
    c.output.success(f"Share {share_id} revoked")
