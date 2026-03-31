"""Deployment commands."""

from __future__ import annotations

import json
import signal
import subprocess
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.runner import run

app = typer.Typer(help="Docker Compose deployment management.")


@app.command()
def build(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to deploy")],
) -> None:
    """Build and deploy an app via Docker Compose."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    compose_file = root / f"docker-compose.{app_name}.yml"
    env_file = root / "env" / f".env.prod.{app_name}"

    if not compose_file.exists():
        out.error(f"Compose file not found: {compose_file}")
        raise typer.Exit(1)
    if not env_file.exists():
        out.error(f"Env file not found: {env_file}")
        raise typer.Exit(1)

    out.info(f"Building and deploying {app_name}...")
    try:
        run(
            ["docker", "compose", "-f", str(compose_file), "--env-file", str(env_file), "up", "-d", "--build"],
            cwd=root,
            capture=False,
            timeout=600,
        )
        out.success(f"{app_name} deployed")
    except Exception as e:
        out.error(f"Deploy failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def status(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show container status for a deployed app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    compose_file = root / f"docker-compose.{app_name}.yml"
    env_file = root / "env" / f".env.prod.{app_name}"

    if not compose_file.exists():
        out.warn(f"No compose file for {app_name}")
        return

    cmd = ["docker", "compose", "-f", str(compose_file)]
    if env_file.exists():
        cmd.extend(["--env-file", str(env_file)])
    cmd.append("ps")

    try:
        run(cmd, cwd=root, capture=False, timeout=30)
    except Exception:
        out.info(f"{app_name}: no containers running")


@app.command()
def logs(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output.")] = True,
) -> None:
    """Show logs for a deployed app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    compose_file = root / f"docker-compose.{app_name}.yml"
    env_file = root / "env" / f".env.prod.{app_name}"

    if not compose_file.exists():
        out.error(f"No compose file for {app_name}")
        raise typer.Exit(1) from None

    cmd = ["docker", "compose", "-f", str(compose_file)]
    if env_file.exists():
        cmd.extend(["--env-file", str(env_file)])
    cmd.append("logs")
    if follow:
        cmd.append("-f")
    cmd.append(app_name)

    try:
        proc = subprocess.Popen(cmd, cwd=root)
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command()
def down(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Stop a deployed app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    compose_file = root / f"docker-compose.{app_name}.yml"
    env_file = root / "env" / f".env.prod.{app_name}"

    if not compose_file.exists():
        out.error(f"No compose file for {app_name}")
        raise typer.Exit(1) from None

    if not force and not typer.confirm(f"Stop deployed app '{app_name}'?"):
        raise typer.Exit(0)

    out.info(f"Stopping {app_name}...")
    cmd = ["docker", "compose", "-f", str(compose_file)]
    if env_file.exists():
        cmd.extend(["--env-file", str(env_file)])
    cmd.append("down")

    try:
        run(cmd, cwd=root, capture=False, timeout=60)
        out.success(f"{app_name} stopped")
    except Exception as e:
        out.error(f"Stop failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def images(ctx: typer.Context) -> None:
    """Show Docker images for all apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        # Check for Dockerfile or compose file
        compose_file = root / f"docker-compose.{name}.yml"
        dockerfile = get_app_dir(root, name) / "Dockerfile"
        has_compose = compose_file.exists()
        has_dockerfile = dockerfile.exists()

        # Check if image exists
        image_name = f"kodemeio-{name}"
        try:
            result = run(
                ["docker", "images", image_name, "--format", "{{.Size}}\t{{.CreatedSince}}"],
                cwd=root,
                capture=True,
                timeout=10,
            )
            if result.stdout.strip():
                line = result.stdout.strip().splitlines()[0]
                parts = line.split("\t")
                img_size = parts[0] if parts else "[dim]--[/dim]"
                img_age = parts[1] if len(parts) > 1 else ""
            else:
                img_size = "[dim]not built[/dim]"
                img_age = ""
        except Exception:
            img_size = "[dim]no docker[/dim]"
            img_age = ""

        def icon(ok: bool) -> str:
            return "[green]OK[/green]" if ok else "[dim]--[/dim]"

        rows.append([name, icon(has_compose), icon(has_dockerfile), img_size, img_age])
        json_data.append(
            {
                "app": name,
                "compose": has_compose,
                "dockerfile": has_dockerfile,
                "image_size": img_size,
                "age": img_age,
            }
        )

    out.table(
        "Docker Images",
        [("App", "cyan"), ("Compose", ""), ("Dockerfile", ""), ("Image Size", "green"), ("Age", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def ps(ctx: typer.Context) -> None:
    """Show all running containers for kodemeio apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    try:
        result = run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Size}}", "--filter", "name=kodemeio"],
            cwd=root,
            capture=True,
            timeout=10,
        )
        if not result.stdout.strip():
            out.info("No kodemeio containers running")
            return

        rows: list[list[str]] = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            rows.append(parts + [""] * (4 - len(parts)))

        out.table(
            "Running Containers",
            [("Name", "cyan"), ("Status", "green"), ("Ports", ""), ("Size", "dim")],
            rows,
        )
    except Exception as e:
        out.error(f"Docker not available: {e}")


@app.command("readiness")
def readiness(ctx: typer.Context) -> None:
    """Show deployment readiness status per app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    from kctl_react.commands.build import _find_build_dir, _format_size, _get_dist_size

    out.info("Checking deployment readiness...")

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)

        build_dir = _find_build_dir(app_dir)
        has_build = build_dir is not None
        build_size = _get_dist_size(build_dir) if build_dir else 0

        has_dockerfile = (app_dir / "Dockerfile").exists()
        has_compose = (app_dir / "docker-compose.yml").exists() or (app_dir / "docker-compose.yaml").exists()
        docker_status = "[green]ready[/green]" if (has_dockerfile or has_compose) else "[dim]no docker[/dim]"

        last_commit = "[dim]unknown[/dim]"
        last_commit_iso = ""
        try:
            result = run(
                ["git", "log", "-1", "--format=%ci", "--", str(get_app_dir(root, name).relative_to(root)) + "/"],
                cwd=root,
                capture=True,
                timeout=10,
            )
            if result.stdout.strip():
                last_commit = result.stdout.strip()[:19]
                last_commit_iso = result.stdout.strip()
        except Exception:
            pass

        pkg_file = app_dir / "package.json"
        has_deploy_script = False
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text())
                has_deploy_script = "deploy" in pkg.get("scripts", {})
            except Exception:
                pass

        has_env = (app_dir / ".env").exists()
        has_env_example = (app_dir / ".env.example").exists()

        build_status = _format_size(build_size) if has_build else "[yellow]not built[/yellow]"

        rows.append([name, build_status, docker_status, last_commit])
        json_data.append(
            {
                "app": name,
                "build": {"built": has_build, "bytes": build_size},
                "docker": {"dockerfile": has_dockerfile, "compose": has_compose},
                "last_commit": last_commit_iso,
                "deploy_script": has_deploy_script,
                "env": has_env,
                "env_example": has_env_example,
            }
        )

    out.table(
        "Deployment Readiness",
        [("App", "cyan"), ("Build", "green"), ("Docker", ""), ("Last Commit", "dim")],
        rows,
        data_for_json=json_data,
    )
