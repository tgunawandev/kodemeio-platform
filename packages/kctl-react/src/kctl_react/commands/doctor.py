"""Top-level doctor command group."""

from __future__ import annotations

import shutil
import subprocess

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Monorepo health checks.")


def _check_cmd(name: str) -> tuple[bool, str]:
    """Check if a command exists and return its version."""
    path = shutil.which(name)
    if not path:
        return False, ""
    try:
        result = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        version = result.stdout.strip().split("\n")[0]
        return True, version
    except Exception:
        return True, "(version unknown)"


def run_doctor(actx: AppContext) -> None:
    """Run comprehensive monorepo health checks.

    Checks: node, pnpm, turbo, git, docker, all apps, packages, env files,
    codegen config, and dependency installation.
    """
    out = actx.output
    root = actx.project_root

    issues = 0
    checks = 0

    def ok(msg: str) -> None:
        nonlocal checks
        checks += 1
        out.success(msg)

    def fail(msg: str) -> None:
        nonlocal checks, issues
        checks += 1
        issues += 1
        out.error(msg)

    def warn(msg: str) -> None:
        nonlocal checks, issues
        checks += 1
        issues += 1
        out.warn(msg)

    out.header("System Tools")

    found, ver = _check_cmd("node")
    if found:
        ok(f"node: {ver}")
    else:
        fail("node: not found")

    found, ver = _check_cmd("pnpm")
    if found:
        ok(f"pnpm: {ver}")
    else:
        fail("pnpm: not found")

    found, ver = _check_cmd("turbo")
    if found:
        ok(f"turbo: {ver}")
    else:
        warn("turbo: not found (optional, runs via pnpm)")

    found, ver = _check_cmd("git")
    if found:
        ok(f"git: {ver}")
    else:
        fail("git: not found")

    found, ver = _check_cmd("docker")
    if found:
        ok(f"docker: {ver}")
    else:
        warn("docker: not found (needed for deploy commands)")

    out.header("Monorepo Structure")

    if (root / "turbo.json").exists():
        ok(f"turbo.json found at {root}")
    else:
        fail(f"turbo.json NOT found at {root}")

    if (root / "package.json").exists():
        ok("Root package.json exists")
    else:
        fail("Root package.json missing")

    if (root / "pnpm-lock.yaml").exists():
        ok("pnpm-lock.yaml exists")
    else:
        fail("pnpm-lock.yaml missing — run `pnpm install`")

    if (root / "node_modules").is_dir():
        ok("node_modules installed")
    else:
        fail("node_modules missing — run `pnpm install`")

    out.header("Apps")

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)
        if not app_dir.is_dir():
            fail(f"{name}: directory missing")
            continue

        problems: list[str] = []
        if not (app_dir / "package.json").exists():
            problems.append("no package.json")
        if not (app_dir / "src").is_dir():
            problems.append("no src/")
        if not (app_dir / "openapi-ts.config.ts").exists():
            problems.append("no openapi-ts.config.ts")

        has_env = (app_dir / ".env").exists() or (app_dir / ".env.local").exists()
        if not has_env:
            problems.append("no .env file")

        if problems:
            warn(f"{name}: {', '.join(problems)}")
        else:
            ok(f"{name}: OK (port {actx.apps[name]['port']})")

    out.header("Shared Packages")

    for pkg_name in actx.packages:
        pkg_dir = root / "packages" / pkg_name
        if not (pkg_dir / "package.json").exists():
            fail(f"@kodemeio/{pkg_name}: package.json missing")
        elif not (pkg_dir / "src").is_dir():
            warn(f"@kodemeio/{pkg_name}: no src/ directory")
        else:
            ok(f"@kodemeio/{pkg_name}: OK")

    out.header("Summary")

    if issues == 0:
        out.success(f"All {checks} checks passed — monorepo is healthy!")
    else:
        out.warn(f"{issues} issue(s) found out of {checks} checks")

    if out.json_mode:
        out.raw_json({"checks": checks, "issues": issues, "healthy": issues == 0})

    if issues > 0:
        raise typer.Exit(1) from None


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Run comprehensive monorepo health checks.

    Checks: node, pnpm, turbo, git, docker, all apps, packages, env files,
    codegen config, and dependency installation.
    """
    actx: AppContext = ctx.obj
    run_doctor(actx)
