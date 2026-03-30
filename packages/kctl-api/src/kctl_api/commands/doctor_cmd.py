"""Environment validation (doctor) commands for kctl-api.

Check, fix, and report on the development environment.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="doctor", help="Environment validation — check, fix, report.", no_args_is_help=True)


def _check_binary(name: str, version_flag: str = "--version") -> dict:
    """Check if a binary is available and get its version."""
    path = shutil.which(name)
    if not path:
        return {"name": name, "ok": False, "version": None, "path": None, "issue": f"{name} not found in PATH"}
    try:
        result = subprocess.run([name, version_flag], capture_output=True, text=True, timeout=5)
        version = (result.stdout or result.stderr).strip().splitlines()[0][:80]
        return {"name": name, "ok": True, "version": version, "path": path}
    except Exception as e:
        return {"name": name, "ok": False, "version": None, "path": path, "issue": str(e)}


def _check_python() -> dict:
    """Check Python version."""
    import sys

    version = sys.version.split()[0]
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 12)
    return {
        "name": "python",
        "ok": ok,
        "version": version,
        "path": sys.executable,
        "issue": None if ok else f"Python 3.12+ required, got {version}",
    }


def _check_env_file() -> dict:
    """Check .env file exists and has required keys."""
    root = find_project_root()
    env_file = root / ".env"
    example_file = root / ".env.example"

    if not env_file.exists():
        return {"name": ".env", "ok": False, "issue": f"{env_file} not found. Copy .env.example"}
    if not example_file.exists():
        return {"name": ".env", "ok": True, "version": "exists (no .env.example to compare)"}

    # Find keys in example but missing in .env
    example_keys = set()
    env_keys = set()

    for line in example_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            example_keys.add(line.split("=")[0].strip())

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_keys.add(line.split("=")[0].strip())

    missing = example_keys - env_keys
    if missing:
        return {
            "name": ".env",
            "ok": False,
            "issue": f"Missing keys: {', '.join(sorted(missing)[:5])}{'...' if len(missing) > 5 else ''}",
        }

    return {"name": ".env", "ok": True, "version": f"{len(env_keys)} keys configured"}


async def _check_postgres_async(actx: AppContext) -> dict:
    """Check PostgreSQL connectivity."""
    db_url = actx.database_url
    if not db_url:
        return {"name": "postgresql", "ok": False, "issue": "No database_url configured"}

    try:
        from kctl_api.core.db import dispose_engine, execute_query

        rows = await execute_query(db_url, "SELECT version()")
        await dispose_engine()
        version = rows[0].get("version", "")[:60] if rows else "unknown"
        return {"name": "postgresql", "ok": True, "version": version}
    except Exception as e:
        return {"name": "postgresql", "ok": False, "issue": str(e)}


async def _check_redis_async(actx: AppContext) -> dict:
    """Check Redis connectivity."""
    redis_url = actx.redis_url
    if not redis_url:
        return {"name": "redis", "ok": False, "issue": "No redis_url configured"}

    try:
        from kctl_api.core.redis import close_redis, get_redis

        client = get_redis(redis_url)
        info = await client.info("server")
        await close_redis()
        version = info.get("redis_version", "unknown") if info else "unknown"
        return {"name": "redis", "ok": True, "version": f"redis {version}"}
    except Exception as e:
        return {"name": "redis", "ok": False, "issue": str(e)}


def _run_all_checks(actx: AppContext) -> list[dict]:
    checks: list[dict] = []

    # Binaries
    checks.append(_check_python())
    checks.append(_check_binary("uv", "--version"))
    checks.append(_check_binary("docker", "--version"))
    checks.append(_check_binary("git", "--version"))

    # Env file
    checks.append(_check_env_file())

    # Services (async)
    checks.append(asyncio.run(_check_postgres_async(actx)))
    checks.append(asyncio.run(_check_redis_async(actx)))

    return checks


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
@app.command()
def check(ctx: typer.Context) -> None:
    """Check Python, uv, Docker, PostgreSQL, Redis, and .env configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running environment checks ...")
    checks = _run_all_checks(actx)

    rows = [
        [
            c["name"],
            "[green]ok[/green]" if c.get("ok") else "[red]fail[/red]",
            c.get("version", ""),
            c.get("issue", ""),
        ]
        for c in checks
    ]

    out.table(
        title="Environment Check",
        columns=[("Check", "bold"), ("Status", ""), ("Version", ""), ("Issue", "red")],
        rows=rows,
        data_for_json=checks,
    )

    failed = [c for c in checks if not c.get("ok")]
    if failed:
        out.warn(f"{len(failed)} check(s) failed. Run: kctl-api doctor fix")
        raise typer.Exit(1)
    else:
        out.success("All checks passed.")


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------
@app.command()
def fix(ctx: typer.Context) -> None:
    """Auto-fix common environment issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    checks = _run_all_checks(actx)
    failed = [c for c in checks if not c.get("ok")]

    if not failed:
        out.success("Nothing to fix — all checks passed.")
        return

    for check_item in failed:
        name = check_item["name"]
        issue = check_item.get("issue", "")
        out.info(f"Fixing: {name} — {issue}")

        if name == ".env":
            env_example = root / ".env.example"
            env_file = root / ".env"
            if not env_file.exists() and env_example.exists():
                import shutil as sh

                sh.copy(env_example, env_file)
                out.success("Copied .env.example → .env")
            else:
                out.warn(f"Manual fix required for .env: {issue}")

        elif name == "uv":
            out.info("Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")

        elif name == "docker":
            out.info("Install Docker: https://docs.docker.com/engine/install/")

        elif name == "python":
            out.info("Install Python 3.12+: https://www.python.org/downloads/")

        elif name in ("postgresql", "redis"):
            out.info("Start services: kctl-api dev up")

        else:
            out.warn(f"No automated fix for {name}. Issue: {issue}")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
@app.command()
def report(ctx: typer.Context) -> None:
    """Generate a full diagnostic report."""
    actx: AppContext = ctx.obj
    out = actx.output

    import datetime
    import platform
    import sys

    out.header("Diagnostic Report")
    out.text(f"  Generated: {datetime.datetime.now(tz=datetime.UTC).isoformat()}")
    out.text(f"  Platform:  {platform.platform()}")
    out.text(f"  Python:    {sys.version}")
    out.text("")

    checks = _run_all_checks(actx)
    passed = [c for c in checks if c.get("ok")]
    failed = [c for c in checks if not c.get("ok")]

    out.text(f"  Checks:    {len(checks)} total, {len(passed)} passed, {len(failed)} failed")
    out.text("")

    for c in checks:
        status = "[green]PASS[/green]" if c.get("ok") else "[red]FAIL[/red]"
        line = f"  {status}  {c['name']}"
        if c.get("version"):
            line += f" ({c['version']})"
        if c.get("issue"):
            line += f" — {c['issue']}"
        out.text(line)

    out.text("")

    # Project info
    root = find_project_root()
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text())
            version = data.get("tool", {}).get("commitizen", {}).get("version", "unknown")
            out.text(f"  Project version: {version}")
        except Exception:
            pass

    out.text(f"  Project root: {root}")

    if actx.json_mode:
        out.raw_json(
            {
                "platform": platform.platform(),
                "python": sys.version,
                "checks": checks,
                "passed": len(passed),
                "failed": len(failed),
            }
        )
