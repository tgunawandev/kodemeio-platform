"""File management commands for kctl-api.

Upload, download, list, and inspect files.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError
from kctl_api.core.utils import human_size

app = typer.Typer(name="files", help="File management — upload, download, list, delete.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_files(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List uploaded files with pagination.

    Note: Requires a file listing endpoint on api-main. If not available,
    falls back to a warning.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get("/api/v1/files", params={"page": page, "per_page": per_page})
    except APIError as e:
        if hasattr(e, "status_code") and e.status_code == 404:
            out.warn("File listing endpoint (GET /api/v1/files) is not available on this server.")
            out.info("Use 'kctl-api files info <id>' to look up individual files.")
            return
        out.error(str(e))
        raise typer.Exit(1) from None
    except (AuthenticationError, KctlConnectionError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for f in items:
        size = f.get("size", 0)
        rows.append(
            [
                str(f.get("id", "")),
                f.get("filename", f.get("name", "")),
                f.get("content_type", ""),
                human_size(size) if isinstance(size, (int, float)) else str(size),
                str(f.get("created_at", "")),
            ]
        )

    out.table(
        title=f"Files (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Filename", ""),
            ("Type", ""),
            ("Size", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------
@app.command()
def info(
    ctx: typer.Context,
    file_id: Annotated[str, typer.Argument(help="File ID.")],
) -> None:
    """Get file metadata by ID."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"/api/v1/files/{file_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"File not found: {file_id}")
        raise typer.Exit(1)

    size = data.get("size", 0)

    out.detail(
        title=f"File: {data.get('filename', file_id)}",
        sections=[
            (
                "Metadata",
                [
                    ("ID", str(data.get("id", ""))),
                    ("Filename", data.get("filename", data.get("name", ""))),
                    ("Content-Type", data.get("content_type", "")),
                    ("Size", human_size(size) if isinstance(size, (int, float)) else str(size)),
                    ("Owner ID", str(data.get("owner_id", ""))),
                ],
            ),
            (
                "Timestamps",
                [
                    ("Created", str(data.get("created_at", ""))),
                    ("Updated", str(data.get("updated_at", ""))),
                ],
            ),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------
@app.command()
def upload(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="Local file path to upload.")],
) -> None:
    """Upload a file via POST /api/v1/files/upload."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.upload("/api/v1/files/upload", file_path)
    except FileNotFoundError:
        out.error(f"File not found: {file_path}")
        raise typer.Exit(1) from None
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"File uploaded: {result.get('filename', file_path)}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------
@app.command()
def download(
    ctx: typer.Context,
    file_id: Annotated[str, typer.Argument(help="File ID to download.")],
    output_path: Annotated[str | None, typer.Option("--output", "-o", help="Output file path.")] = None,
) -> None:
    """Download a file by ID via GET /api/v1/files/{id}/download."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        import httpx

        url = f"{actx.client.base_url}/api/v1/files/{file_id}/download"
        headers = actx.client._auth_headers()
        with httpx.stream("GET", url, headers=headers, follow_redirects=True) as response:
            response.raise_for_status()
            # Determine output filename
            dest = output_path or f"file_{file_id}"
            content_disp = response.headers.get("content-disposition", "")
            if not output_path and "filename=" in content_disp:
                dest = content_disp.split("filename=")[-1].strip('"')
            with open(dest, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        out.success(f"Downloaded to {dest}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Download failed: {e}")
        raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command()
def delete(
    ctx: typer.Context,
    file_id: Annotated[str, typer.Argument(help="File ID to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete a file by ID via DELETE /api/v1/files/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(f"Delete file {file_id}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        result = actx.client.delete(f"/api/v1/files/{file_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"File {file_id} deleted.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
@app.command()
def stats(ctx: typer.Context) -> None:
    """Get file storage statistics via GET /api/v1/files/stats."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get("/api/v1/files/stats")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.info("No stats available.")
        return

    out.detail(
        title="File Storage Stats",
        sections=[
            (
                "Summary",
                [(k, str(v)) for k, v in data.items()],
            ),
        ],
        data_for_json=data,
    )
