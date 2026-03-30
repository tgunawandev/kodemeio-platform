"""Docker management commands for kctl-api.

Image management, container inspection, network, volumes, and system info.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(
    name="docker", help="Docker management — images, containers, network, volumes, system.", no_args_is_help=True
)


def _compose_cmd(args: list[str], compose_file: str | None = None) -> list[str]:
    root = find_project_root()
    cf = compose_file or str(root / "docker-compose.yml")
    return ["docker", "compose", "-f", cf, *args]


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------
@app.command()
def images(ctx: typer.Context) -> None:
    """List Docker images for the project."""
    actx: AppContext = ctx.obj
    out = actx.output

    result = subprocess.run(
        ["docker", "images", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.error(f"docker images failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    image_list: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                image_list.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Filter to project images
    root = find_project_root()
    project_name = root.name.replace("-", "")

    project_images = [
        img
        for img in image_list
        if project_name in (img.get("Repository") or "").lower() or "kodemeio" in (img.get("Repository") or "").lower()
    ] or image_list[:20]

    rows = [
        [
            img.get("Repository", ""),
            img.get("Tag", ""),
            img.get("Size", ""),
            img.get("CreatedSince", img.get("CreatedAt", "")),
        ]
        for img in project_images
    ]
    out.table(
        title=f"Docker Images ({len(project_images)})",
        columns=[("Repository", "bold"), ("Tag", ""), ("Size", ""), ("Created", "")],
        rows=rows,
        data_for_json=project_images,
    )


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------
@app.command()
def containers(
    ctx: typer.Context,
    all_containers: Annotated[bool, typer.Option("--all", "-a", help="Show stopped containers too.")] = False,
) -> None:
    """List running (or all) Docker containers."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = ["docker", "ps", "--format", "json"]
    if all_containers:
        cmd.append("--all")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"docker ps failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    container_list: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                container_list.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows = [
        [
            c.get("Names", c.get("Name", "")),
            c.get("Image", ""),
            c.get("Status", ""),
            c.get("Ports", ""),
        ]
        for c in container_list
    ]
    out.table(
        title=f"Containers ({len(container_list)})",
        columns=[("Name", "bold"), ("Image", ""), ("Status", ""), ("Ports", "")],
        rows=rows,
        data_for_json=container_list,
    )


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------
@app.command()
def network(ctx: typer.Context) -> None:
    """List Docker networks and show which containers are attached."""
    actx: AppContext = ctx.obj
    out = actx.output

    result = subprocess.run(
        ["docker", "network", "ls", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.error(f"docker network ls failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    networks: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                networks.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows = [
        [
            n.get("Name", ""),
            n.get("Driver", ""),
            n.get("Scope", ""),
            "[green]yes[/green]" if n.get("Name") == "dokploy-network" else "",
        ]
        for n in networks
    ]
    out.table(
        title=f"Docker Networks ({len(networks)})",
        columns=[("Name", "bold"), ("Driver", ""), ("Scope", ""), ("Dokploy", "")],
        rows=rows,
        data_for_json=networks,
    )

    # Check dokploy-network
    has_dokploy = any(n.get("Name") == "dokploy-network" for n in networks)
    if not has_dokploy:
        out.warn("dokploy-network not found. Create it: docker network create dokploy-network")


# ---------------------------------------------------------------------------
# volumes
# ---------------------------------------------------------------------------
@app.command()
def volumes(ctx: typer.Context) -> None:
    """List Docker volumes used by the project."""
    actx: AppContext = ctx.obj
    out = actx.output

    result = subprocess.run(
        ["docker", "volume", "ls", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.error(f"docker volume ls failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    volume_list: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                volume_list.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows = [[v.get("Name", ""), v.get("Driver", ""), v.get("Labels", "")] for v in volume_list]
    out.table(
        title=f"Docker Volumes ({len(volume_list)})",
        columns=[("Name", "bold"), ("Driver", ""), ("Labels", "")],
        rows=rows,
        data_for_json=volume_list,
    )


# ---------------------------------------------------------------------------
# system
# ---------------------------------------------------------------------------
@app.command()
def system(ctx: typer.Context) -> None:
    """Show Docker system disk usage and resource summary."""
    actx: AppContext = ctx.obj
    out = actx.output

    result = subprocess.run(
        ["docker", "system", "df"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.error(f"docker system df failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    out.text(result.stdout)

    # Also show info summary
    info_result = subprocess.run(
        [
            "docker",
            "info",
            "--format",
            "Containers: {{.Containers}} running / Images: {{.Images}} / Memory: {{.MemTotal}}",
        ],
        capture_output=True,
        text=True,
    )
    if info_result.returncode == 0:
        out.text(info_result.stdout.strip())

    if actx.json_mode:
        out.raw_json({"output": result.stdout})
