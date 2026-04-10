"""File attachment commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="File attachment management.")


@app.command()
def create(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="File path to upload", exists=True)],
    document_id: Annotated[Optional[str], typer.Option("--document-id", "-d", help="Document ID to associate")] = None,
) -> None:
    """Upload a file attachment."""
    c: AppContext = ctx.obj

    # Outline attachments.create expects multipart upload
    # We need to use a raw request since the client's post() sends JSON
    import httpx

    files = {"file": (file.name, file.open("rb"), "application/octet-stream")}
    data: dict = {}
    if document_id:
        data["documentId"] = document_id

    # Build the request manually since we need multipart
    url = "attachments.create"
    endpoint = url.lstrip("/")
    try:
        # Remove Content-Type header for multipart (httpx sets it automatically)
        headers = dict(c.client._client.headers)
        headers.pop("content-type", None)
        headers.pop("Content-Type", None)

        response = c.client._client.post(
            endpoint,
            files=files,
            data=data,
            headers=headers,
        )
    except httpx.HTTPError as e:
        c.output.error(f"Upload failed: {e}")
        raise typer.Exit(1)

    if response.status_code >= 400:
        c.output.error(f"Upload failed: HTTP {response.status_code}")
        raise typer.Exit(1)

    result = response.json()
    attachment = result.get("data", {})
    attachment_data = attachment.get("attachment", attachment)

    c.output.detail(
        "Attachment Uploaded",
        [
            (
                "Details",
                [
                    ("ID", str(attachment_data.get("id", ""))),
                    ("Name", str(attachment_data.get("name", file.name))),
                    ("Size", str(attachment_data.get("size", ""))),
                    ("Content Type", str(attachment_data.get("contentType", ""))),
                    ("URL", str(attachment_data.get("url", attachment.get("url", "")))),
                ],
            )
        ],
        data_for_json=result,
    )


@app.command()
def redirect(
    ctx: typer.Context,
    attachment_id: Annotated[str, typer.Argument(help="Attachment ID")],
) -> None:
    """Get the redirect URL for an attachment."""
    c: AppContext = ctx.obj
    result = c.client.post("attachments.redirect", data={"id": attachment_id})

    # The API may return a redirect URL or the data directly
    url = ""
    if isinstance(result, dict):
        url = result.get("url", result.get("data", {}).get("url", ""))

    if url:
        c.output.success(f"Attachment URL: {url}")
    else:
        c.output.detail("Attachment Redirect", [("Result", [("Response", str(result))])], data_for_json=result)
