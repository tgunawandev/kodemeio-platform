"""Patch management commands for compose/application services."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage file patches for services.")


@app.command("list")
def list_(
    ctx: typer.Context,
    entity_id: Annotated[str, typer.Argument(help="Compose or application ID")],
    entity_type: Annotated[str, typer.Option("--type", "-t", help="Type: compose or application")] = "compose",
) -> None:
    """List all patches for a service."""
    c: AppContext = ctx.obj
    patches = c.client.get("/patch.byEntityId", params={"id": entity_id, "type": entity_type})
    if not isinstance(patches, list):
        patches = []
    rows = []
    for p in patches:
        pid = p.get("patchId", "")[:12]
        name = p.get("name", p.get("filePath", ""))
        enabled = str(p.get("enabled", "-"))
        created = p.get("createdAt", "-")
        rows.append([pid, name, enabled, str(created)])
    c.output.table(
        f"Patches ({len(patches)})",
        [("ID", "dim"), ("Name/Path", "cyan"), ("Enabled", ""), ("Created", "dim")],
        rows,
        data_for_json=patches,
    )


@app.command()
def get(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Argument(help="Patch ID")],
) -> None:
    """Get patch details."""
    c: AppContext = ctx.obj
    data = c.client.get("/patch.one", params={"patchId": patch_id})
    if not isinstance(data, dict):
        c.output.error(f"Patch '{patch_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Patch",
            [
                ("ID", data.get("patchId", "")),
                ("Name", data.get("name", "-")),
                ("File Path", data.get("filePath", "-")),
                ("Enabled", str(data.get("enabled", "-"))),
                ("Compose ID", data.get("composeId", "-")),
                ("Application ID", data.get("applicationId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    patch_content = data.get("patchContent", data.get("content", ""))
    if patch_content:
        sections.append(("Content", [("Patch", str(patch_content)[:500])]))
    c.output.detail(f"Patch: {data.get('name', patch_id)}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    compose_id: Annotated[str | None, typer.Option("--compose", "-c", help="Compose ID")] = None,
    application_id: Annotated[str | None, typer.Option("--application", "-a", help="Application ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Patch name")] = None,
    file_path: Annotated[str | None, typer.Option("--path", help="Target file path in container")] = None,
    content: Annotated[str | None, typer.Option("--content", help="Patch content")] = None,
    content_file: Annotated[str | None, typer.Option("--file", "-f", help="Read content from file")] = None,
) -> None:
    """Create a new patch."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if compose_id:
        payload["composeId"] = compose_id
    if application_id:
        payload["applicationId"] = application_id
    if name:
        payload["name"] = name
    if file_path:
        payload["filePath"] = file_path
    if content_file:
        import pathlib

        content = pathlib.Path(content_file).read_text()
    if content:
        payload["patchContent"] = content
    result = c.client.post("/patch.create", json=payload)
    pid = result.get("patchId", "") if isinstance(result, dict) else ""
    c.output.success(f"Patch created: {pid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Argument(help="Patch ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    content: Annotated[str | None, typer.Option("--content", help="New patch content")] = None,
    content_file: Annotated[str | None, typer.Option("--file", "-f", help="Read content from file")] = None,
) -> None:
    """Update a patch."""
    c: AppContext = ctx.obj
    payload: dict = {"patchId": patch_id}
    if name:
        payload["name"] = name
    if content_file:
        import pathlib

        payload["patchContent"] = pathlib.Path(content_file).read_text()
    elif content:
        payload["patchContent"] = content
    if len(payload) == 1:
        c.output.error("Nothing to update. Provide --name, --content, or --file.")
        raise typer.Exit(1)
    result = c.client.post("/patch.update", json=payload)
    c.output.success(f"Patch '{patch_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Argument(help="Patch ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a patch (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete patch '{patch_id}'?", abort=True)
    result = c.client.post("/patch.delete", json={"patchId": patch_id})
    c.output.success(f"Patch '{patch_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def toggle(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Argument(help="Patch ID")],
) -> None:
    """Toggle a patch enabled/disabled."""
    c: AppContext = ctx.obj
    result = c.client.post("/patch.toggleEnabled", json={"patchId": patch_id})
    c.output.success(f"Patch '{patch_id}' toggled")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("save-file")
def save_file(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Option("--patch", "-p", help="Patch ID")],
    file_path: Annotated[str, typer.Option("--path", help="File path in container")],
    content: Annotated[str | None, typer.Option("--content", help="File content")] = None,
    content_file: Annotated[str | None, typer.Option("--file", "-f", help="Read content from local file")] = None,
) -> None:
    """Save a file as a patch."""
    c: AppContext = ctx.obj
    if content_file:
        import pathlib

        content = pathlib.Path(content_file).read_text()
    if not content:
        c.output.error("Provide --content or --file")
        raise typer.Exit(1)
    result = c.client.post(
        "/patch.saveFileAsPatch",
        json={"patchId": patch_id, "filePath": file_path, "content": content},
    )
    c.output.success(f"File saved as patch: {file_path}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("read-file")
def read_file(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Option("--patch", "-p", help="Patch ID")],
    file_path: Annotated[str, typer.Option("--path", help="File path to read")],
) -> None:
    """Read a file from the patch repo."""
    c: AppContext = ctx.obj
    data = c.client.get("/patch.readRepoFile", params={"patchId": patch_id, "filePath": file_path})
    content = data if isinstance(data, str) else data.get("content", str(data)) if isinstance(data, dict) else str(data)
    if c.json_mode:
        c.output.raw_json({"filePath": file_path, "content": content})
    else:
        c.output.header(f"File: {file_path}")
        c.output.text(str(content))


@app.command("read-dirs")
def read_dirs(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Option("--patch", "-p", help="Patch ID")],
) -> None:
    """List directories in the patch repo."""
    c: AppContext = ctx.obj
    data = c.client.get("/patch.readRepoDirectories", params={"patchId": patch_id})
    if not isinstance(data, list):
        data = [data] if data else []
    rows = [[str(d)] for d in data]
    c.output.table(
        "Patch Repo Directories",
        [("Path", "cyan")],
        rows,
        data_for_json=data,
    )


@app.command("mark-delete")
def mark_delete(
    ctx: typer.Context,
    patch_id: Annotated[str, typer.Option("--patch", "-p", help="Patch ID")],
    file_path: Annotated[str, typer.Option("--path", help="File path to mark for deletion")],
) -> None:
    """Mark a file for deletion in the patch."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "/patch.markFileForDeletion",
        json={"patchId": patch_id, "filePath": file_path},
    )
    c.output.success(f"File '{file_path}' marked for deletion")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("clean")
def clean(
    ctx: typer.Context,
    compose_id: Annotated[str | None, typer.Option("--compose", "-c", help="Compose ID")] = None,
    application_id: Annotated[str | None, typer.Option("--application", "-a", help="Application ID")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Clean patch repos (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm("Clean all patch repos? This cannot be undone.", abort=True)
    payload: dict = {}
    if compose_id:
        payload["composeId"] = compose_id
    if application_id:
        payload["applicationId"] = application_id
    result = c.client.post("/patch.cleanPatchRepos", json=payload)
    c.output.success("Patch repos cleaned")
    if c.json_mode:
        c.output.raw_json(result)
