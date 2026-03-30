"""kctl-claude setup — deploy Claude Code to local, VPS, or Docker."""

from __future__ import annotations

import subprocess

import typer
from kctl_common.exceptions import CommandError

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.runner import run_script

app = typer.Typer(help="Setup Claude Code on local, VPS, or Docker.")


@app.command()
def local(ctx: typer.Context) -> None:
    """Setup local development environment (laptop)."""
    actx: AppContext = ctx.obj
    out = actx.output
    script = _get_script(actx, "setup-local.sh")
    try:
        run_script(script, capture=False)
        out.success("Local setup complete")
    except CommandError as e:
        out.error(f"Setup failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def vps(
    ctx: typer.Context,
    check: bool = typer.Option(False, "--check", help="Dry-run: show what would install"),
    skip_repos: bool = typer.Option(False, "--skip-repos", help="Skip repo cloning"),
) -> None:
    """Setup VPS/bare-metal server (requires sudo)."""
    actx: AppContext = ctx.obj
    out = actx.output
    script = _get_script(actx, "setup-vps.sh")
    args = []
    if check:
        args.append("--check")
    if skip_repos:
        args.append("--skip-repos")
    # VPS setup requires sudo
    cmd = ["sudo", "bash", str(script)] + args
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        out.error(f"VPS setup failed (exit {result.returncode})")
        raise typer.Exit(code=1)
    out.success("VPS setup complete")


@app.command()
def docker(ctx: typer.Context) -> None:
    """Show Docker deployment commands."""
    actx: AppContext = ctx.obj
    out = actx.output

    if actx.json_mode:
        out.raw_json(
            {
                "production": "docker compose -f docker-compose.prod.yml up -d",
                "sdk_only": "docker compose -f docker-compose.sdk.yml up -d",
                "local": "docker compose up -d",
            }
        )
        return

    out.header("DOCKER DEPLOYMENT")
    out.text("")
    out.text("  [bold]Production (full dev container):[/bold]")
    out.text("    docker compose -f docker-compose.prod.yml build")
    out.text("    docker compose -f docker-compose.prod.yml up -d")
    out.text("")
    out.text("  [bold]SDK-only (lightweight API):[/bold]")
    out.text("    docker compose -f docker-compose.sdk.yml build")
    out.text("    docker compose -f docker-compose.sdk.yml up -d")
    out.text("")
    out.text("  [bold]Local dev:[/bold]")
    out.text("    docker compose up -d")
    out.text("")
    out.text("  [bold]Before deploying:[/bold]")
    out.text("    kctl-claude env check      # Validate .env")
    out.text("    kctl-claude sync push      # Sync config to repo")
    out.text("    git push                   # Dokploy auto-deploys")
    out.text("")


@app.command("init")
def init_session(ctx: typer.Context) -> None:
    """Run session initialization (git, SSH, tmux, kctl tools).

    Note: for shell-affecting steps (SSH agent, env vars), source directly:
      source scripts/init-session.sh
    """
    actx: AppContext = ctx.obj
    out = actx.output
    script = _get_script(actx, "init-session.sh")
    try:
        run_script(script, capture=False)
        out.success("Session initialized")
    except CommandError as e:
        out.error(f"Init failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def compare(ctx: typer.Context) -> None:
    """Compare setup modes side-by-side."""
    actx: AppContext = ctx.obj
    out = actx.output

    if actx.json_mode:
        out.raw_json(
            {
                "modes": {
                    "local": {
                        "command": "kctl-claude setup local",
                        "config_sync": "manual (kctl-claude sync push/pull)",
                        "sdk_api": "optional (ENABLE_SDK_API=true)",
                        "isolation": "none (your laptop)",
                        "bypass_permissions": False,
                    },
                    "docker": {
                        "command": "docker compose -f docker-compose.prod.yml up -d",
                        "config_sync": "baked into image at build time",
                        "sdk_api": "optional (ENABLE_SDK_API=true)",
                        "isolation": "container (non-root dev user)",
                        "bypass_permissions": True,
                    },
                    "vps": {
                        "command": "sudo kctl-claude setup vps",
                        "config_sync": "init-session.sh at login",
                        "sdk_api": "systemd service",
                        "isolation": "server (non-root dev user)",
                        "bypass_permissions": True,
                    },
                }
            }
        )
        return

    out.header("DEPLOYMENT MODES")
    out.table(
        "Comparison",
        [("", "dim"), ("Local", "green"), ("Docker", "cyan"), ("VPS", "yellow")],
        [
            ["Setup", "kctl-claude setup local", "docker compose up", "sudo kctl-claude setup vps"],
            ["Target", "Laptop / workstation", "Hetzner via Dokploy", "Any Ubuntu server"],
            ["Config sync", "manual push/pull", "Baked at build", "init-session.sh"],
            ["SDK API", "Optional", "Optional", "systemd service"],
            ["Isolation", "None", "Container", "dev user + sudo"],
            ["Permissions", "Normal", "Bypass", "Bypass"],
            ["kctl tools", "uv install", "entrypoint.sh", "setup-vps.sh"],
            ["Repos", "Your local dirs", "Bind-mounted", "Cloned to /opt/dev"],
        ],
    )


def _get_script(actx: AppContext, name: str):  # noqa: ANN202
    repo = actx.repo_dir
    if not repo:
        actx.output.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / name
    if not script.is_file():
        actx.output.error(f"Script not found: {script}")
        raise typer.Exit(code=1)
    return script
