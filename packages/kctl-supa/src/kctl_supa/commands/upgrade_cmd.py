"""Supabase version upgrade management for kctl-supa."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext

app = typer.Typer(help="Upgrade Supabase versions.")

OFFICIAL_COMPOSE_URL = "https://raw.githubusercontent.com/supabase/supabase/master/docker/docker-compose.yml"

SERVICE_IMAGE_MAP = {
    "studio": "supabase/studio",
    "auth": "supabase/gotrue",
    "rest": "postgrest/postgrest",
    "realtime": "supabase/realtime",
    "storage": "supabase/storage-api",
    "meta": "supabase/postgres-meta",
    "analytics": "supabase/logflare",
    "imgproxy": "darthsim/imgproxy",
    "db": "supabase/postgres",
    "kong": "kong",
    "functions": "supabase/edge-runtime",
    "vector": "timberio/vector",
    "supavisor": "supabase/supavisor",
}

IMAGE_ALIASES = {
    "kong/kong": "kong",
    "kong": "kong/kong",
}


def _fetch_official_versions() -> dict[str, str]:
    resp = httpx.get(OFFICIAL_COMPOSE_URL, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    versions: dict[str, str] = {}
    for line in resp.text.splitlines():
        m = re.match(r"\s*image:\s*(.+)", line)
        if m:
            full = m.group(1).strip()
            if ":" in full:
                repo, tag = full.rsplit(":", 1)
                versions[repo] = tag
    return versions


def _get_local_versions(project_dir: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    compose = project_dir / "docker-compose.prod.yml"
    if compose.exists():
        for line in compose.read_text().splitlines():
            m = re.match(r"\s*image:\s*(.+)", line)
            if m:
                full = m.group(1).strip()
                if ":" in full:
                    repo, tag = full.rsplit(":", 1)
                    versions[repo] = tag

    docker_dir = project_dir / "docker"
    if docker_dir.is_dir():
        for dockerfile in docker_dir.rglob("Dockerfile"):
            for line in dockerfile.read_text().splitlines():
                m = re.match(r"^FROM\s+(.+)", line, re.IGNORECASE)
                if m:
                    full = m.group(1).strip()
                    if ":" in full:
                        repo, tag = full.rsplit(":", 1)
                        versions[repo] = tag
    return versions


def _find_project_dir(actx: AppContext) -> Path:
    candidates = [
        Path.cwd(),
        Path.home() / "project/00-new-projects/terakidz-workspace/terakidz-supabase",
    ]
    for p in candidates:
        if (p / "docker-compose.prod.yml").exists():
            return p
    return Path.cwd()


@app.command()
def check(
    ctx: typer.Context,
    project_dir: Annotated[str, typer.Option("--dir", "-d", help="Project directory")] = "",
) -> None:
    """Compare local versions against latest official Supabase release."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching latest official Supabase versions...")
    try:
        official = _fetch_official_versions()
    except Exception as exc:
        out.error(f"Failed to fetch official versions: {exc}")
        raise typer.Exit(1) from exc

    pdir = Path(project_dir) if project_dir else _find_project_dir(actx)
    local = _get_local_versions(pdir)

    table = Table(title="Supabase Version Check", show_header=True, header_style="bold cyan")
    table.add_column("Service", style="cyan")
    table.add_column("Current")
    table.add_column("Latest")
    table.add_column("Status")

    upgrades_available = 0
    for name, repo in sorted(SERVICE_IMAGE_MAP.items(), key=lambda x: x[0]):
        current = local.get(repo) or local.get(IMAGE_ALIASES.get(repo, ""), "not found")
        latest = official.get(repo) or official.get(IMAGE_ALIASES.get(repo, ""), "unknown")

        if current == "not found":
            status = "[dim]not tracked[/dim]"
        elif current == latest:
            status = "[green]up to date[/green]"
        else:
            status = "[yellow]upgrade available[/yellow]"
            upgrades_available += 1

        table.add_row(name, current, latest, status)

    rprint(table)

    if upgrades_available > 0:
        out.warn(f"{upgrades_available} upgrade(s) available. Run: kctl-supa upgrade apply")
    else:
        out.success("All services are up to date!")


@app.command()
def apply(
    ctx: typer.Context,
    project_dir: Annotated[str, typer.Option("--dir", "-d", help="Project directory")] = "",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without applying")] = False,
    service: Annotated[str, typer.Option("--service", "-s", help="Upgrade specific service only")] = "",
) -> None:
    """Update compose + Dockerfiles to latest official Supabase versions."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching latest official Supabase versions...")
    try:
        official = _fetch_official_versions()
    except Exception as exc:
        out.error(f"Failed to fetch official versions: {exc}")
        raise typer.Exit(1) from exc

    pdir = Path(project_dir) if project_dir else _find_project_dir(actx)
    changes: list[tuple[str, str, str, str]] = []

    compose_files = [pdir / "docker-compose.prod.yml", pdir / "docker-compose.yml"]
    for compose in compose_files:
        if not compose.exists():
            continue
        content = compose.read_text()
        new_content = content
        for repo, latest_tag in official.items():
            if service and not any(repo == SERVICE_IMAGE_MAP.get(service, "")):
                continue
            pattern = re.compile(rf"(image:\s*{re.escape(repo)}:)(\S+)")
            for m in pattern.finditer(content):
                current_tag = m.group(2)
                if current_tag != latest_tag:
                    new_content = new_content.replace(f"{repo}:{current_tag}", f"{repo}:{latest_tag}")
                    changes.append((compose.name, repo, current_tag, latest_tag))

        if new_content != content:
            if not dry_run:
                compose.write_text(new_content)

    docker_dir = pdir / "docker"
    if docker_dir.is_dir():
        for dockerfile in docker_dir.rglob("Dockerfile"):
            content = dockerfile.read_text()
            new_content = content
            for repo, latest_tag in official.items():
                if service and not any(repo == SERVICE_IMAGE_MAP.get(service, "")):
                    continue
                pattern = re.compile(rf"(FROM\s+{re.escape(repo)}:)(\S+)", re.IGNORECASE)
                for m in pattern.finditer(content):
                    current_tag = m.group(2)
                    if current_tag != latest_tag:
                        new_content = new_content.replace(f"{repo}:{current_tag}", f"{repo}:{latest_tag}")
                        rel_path = dockerfile.relative_to(pdir)
                        changes.append((str(rel_path), repo, current_tag, latest_tag))

            if new_content != content:
                if not dry_run:
                    dockerfile.write_text(new_content)

    if not changes:
        out.success("All versions are already up to date!")
        return

    table = Table(
        title="Upgrade Changes" + (" (DRY RUN)" if dry_run else ""),
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("File", style="cyan")
    table.add_column("Image")
    table.add_column("From")
    table.add_column("To", style="green")

    for file, repo, old, new in changes:
        table.add_row(file, repo.split("/")[-1], old, new)

    rprint(table)

    if dry_run:
        out.info("Dry run — no files changed. Remove --dry-run to apply.")
    else:
        out.success(f"{len(changes)} version(s) updated across {len(set(c[0] for c in changes))} file(s).")
        out.info("Next steps:")
        typer.echo("  1. git add -A && git commit -m 'chore: upgrade Supabase versions'")
        typer.echo("  2. git push origin main")
        typer.echo("  3. kctl-dokploy -p kodemeio compose redeploy z8sT_TmJ40OsYjCZ44X8g")


@app.command()
def versions(ctx: typer.Context) -> None:
    """Show current running service versions from the live instance."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_supa.core.docker import DockerOps

    try:
        docker = DockerOps(actx.config)
        containers = docker.container_status()
        docker.close()
    except Exception as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    table = Table(title="Running Versions", show_header=True, header_style="bold cyan")
    table.add_column("Container", style="cyan")
    table.add_column("Image")
    table.add_column("Status")

    for c in sorted(containers, key=lambda x: x.get("Names", "")):
        name = c.get("Names", "")
        image = c.get("Image", "")
        status = c.get("Status", "")
        short_name = name.rsplit("-", 1)[0].split("-")[-1] if "-" in name else name
        table.add_row(short_name, image, status)

    rprint(table)
