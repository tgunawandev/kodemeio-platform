"""Security audit and credential management commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile

app = typer.Typer(help="Security audit and credential management.")


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, skipping comments and blank lines."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


_PLACEHOLDER_PATTERNS = ("changeme", "your_", "replace_", "todo", "example", "placeholder", "xxx")


@app.command()
def audit(ctx: typer.Context) -> None:
    """Run the 15-point security audit script."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    script = root / "scripts" / "security-audit.sh"
    if not script.exists():
        out.warn(f"Security audit script not found: {script}")
        out.info("Run manually: bash scripts/security-audit.sh")
        return

    out.info("Running security audit...")
    try:
        result = subprocess.run(
            ["bash", str(script)],
            cwd=str(root),
            capture_output=False,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            out.success("Security audit passed.")
        else:
            out.warn(f"Security audit exited with code {result.returncode}")
    except subprocess.TimeoutExpired as e:
        out.error("Security audit timed out after 120 seconds.")
        raise typer.Exit(1) from e
    except OSError as e:
        out.error(f"Failed to run audit script: {e}")
        raise typer.Exit(1) from e


@app.command()
def credentials(ctx: typer.Context) -> None:
    """Check .env.prod for empty or placeholder values."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    prod_path = root / ".env.prod"
    if not prod_path.exists():
        out.error(".env.prod not found")
        raise typer.Exit(1)

    prod = _parse_env_file(prod_path)

    issues = []
    rows = []
    json_data = []

    for key, value in sorted(prod.items()):
        if not value:
            status = "EMPTY"
            issues.append(key)
        elif any(p in value.lower() for p in _PLACEHOLDER_PATTERNS):
            status = "PLACEHOLDER"
            issues.append(key)
        else:
            status = "OK"

        rows.append([key, status])
        json_data.append({"key": key, "status": status})

    out.table(
        f"Credentials Check ({len(prod)} vars, {len(issues)} issue(s))",
        [("Key", "cyan"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if issues:
        out.warn(f"{len(issues)} credential(s) need attention: {', '.join(issues)}")
        raise typer.Exit(1)
    else:
        out.success("All credentials are set.")


@app.command()
def allowlist(ctx: typer.Context) -> None:
    """Show the Telegram allowlist (DMs and groups)."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    data = mgr.read(ConfigFile.OPENCLAW)
    allow_from = data.get("channels", {}).get("telegram", {}).get("allowFrom", {})

    dm_ids = allow_from.get("dm", [])
    group_ids = allow_from.get("groups", [])

    rows = []
    json_data = []
    for uid in dm_ids:
        rows.append([str(uid), "dm"])
        json_data.append({"id": uid, "type": "dm"})
    for uid in group_ids:
        rows.append([str(uid), "group"])
        json_data.append({"id": uid, "type": "group"})

    out.table(
        f"Security Allowlist ({len(rows)} entries)",
        [("ID", "cyan"), ("Type", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def sandbox(ctx: typer.Context) -> None:
    """Show agent sandbox settings."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    data = mgr.read(ConfigFile.OPENCLAW)
    agents = data.get("agents", {}).get("list", [])
    defaults = data.get("agents", {}).get("defaults", {})
    default_sandbox = defaults.get("sandbox", True)

    rows = []
    json_data = []
    for agent in agents:
        name = agent.get("name", "")
        sandboxed = agent.get("sandbox", default_sandbox)
        status = "sandboxed" if sandboxed else "UNRESTRICTED"
        rows.append([name, str(sandboxed), status])
        json_data.append({"name": name, "sandbox": sandboxed, "status": status})

    out.table(
        f"Agent Sandbox Settings (default: {default_sandbox})",
        [("Agent", "cyan"), ("Sandbox", ""), ("Status", "dim")],
        rows,
        data_for_json=json_data,
    )
