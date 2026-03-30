"""Dependency management commands for kctl-api.

Audit, outdated, licenses, graph, and size analysis.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(
    name="deps", help="Dependency management — audit, outdated, licenses, graph, size.", no_args_is_help=True
)


def _run_uv(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", *args], capture_output=True, text=True, cwd=cwd)


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
@app.command()
def audit(
    ctx: typer.Context,
    fix: Annotated[bool, typer.Option("--fix", help="Attempt to upgrade vulnerable packages.")] = False,
) -> None:
    """Run security audit via uv or pip-audit."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    out.info("Running dependency security audit ...")

    # Try pip-audit first (more detailed), fall back to uv
    import shutil

    if shutil.which("pip-audit"):
        cmd = ["pip-audit", "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))

        if result.returncode == 0:
            import json

            try:
                data = json.loads(result.stdout)
                vulns = data.get("vulnerabilities", [])
                if not vulns:
                    out.success("No vulnerabilities found (pip-audit).")
                    return

                rows = [
                    [v.get("name", ""), v.get("version", ""), v.get("id", ""), v.get("fix_versions", [""])[0]]
                    for v in vulns
                ]
                out.table(
                    title=f"Vulnerabilities ({len(vulns)})",
                    columns=[("Package", "bold"), ("Version", ""), ("ID", "red"), ("Fix Version", "green")],
                    rows=rows,
                    data_for_json=vulns,
                )
                raise typer.Exit(1)
            except Exception:
                pass

        out.text(result.stdout)
        if result.returncode != 0:
            out.text(result.stderr)
    else:
        # Fall back to uv audit (uv >= 0.4)
        result = _run_uv(["audit"], cwd=str(root))
        if result.returncode == 0 and not result.stdout.strip():
            out.success("No vulnerabilities found (uv audit).")
        else:
            out.text(result.stdout)
            if result.stderr:
                out.text(result.stderr)
            out.info("For detailed audit: uv add --dev pip-audit && pip-audit")


# ---------------------------------------------------------------------------
# outdated
# ---------------------------------------------------------------------------
@app.command()
def outdated(ctx: typer.Context) -> None:
    """Show outdated packages across all workspace members."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    out.info("Checking for outdated packages ...")

    result = _run_uv(["pip", "list", "--outdated", "--format", "json"], cwd=str(root))

    if result.returncode != 0:
        # Try without --format json
        result = _run_uv(["pip", "list", "--outdated"], cwd=str(root))
        out.text(result.stdout or "(no output)")
        return

    import json

    try:
        packages = json.loads(result.stdout)
    except Exception:
        out.text(result.stdout or "(no output)")
        return

    if not packages:
        out.success("All packages are up to date.")
        return

    rows = [[p.get("name", ""), p.get("version", ""), p.get("latest_version", "")] for p in packages]
    out.table(
        title=f"Outdated Packages ({len(packages)})",
        columns=[("Package", "bold"), ("Current", "yellow"), ("Latest", "green")],
        rows=rows,
        data_for_json=packages,
    )
    out.info("Upgrade: uv sync --upgrade")


# ---------------------------------------------------------------------------
# licenses
# ---------------------------------------------------------------------------
@app.command()
def licenses(
    ctx: typer.Context,
    allow: Annotated[str | None, typer.Option("--allow", help="Comma-separated allowed license patterns.")] = None,
) -> None:
    """Generate a license report for all installed packages."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    # Try pip-licenses
    import shutil

    if shutil.which("pip-licenses"):
        result = subprocess.run(["pip-licenses", "--format", "json"], capture_output=True, text=True, cwd=str(root))
        if result.returncode == 0:
            import json

            try:
                data = json.loads(result.stdout)
                allowed_list = [a.strip().upper() for a in (allow or "").split(",")] if allow else []

                flagged = []
                for pkg in data:
                    lic = pkg.get("License", "UNKNOWN").upper()
                    if allowed_list and not any(a in lic for a in allowed_list):
                        flagged.append(pkg)

                display = flagged if (allowed_list and flagged) else data
                rows = [[p.get("Name", ""), p.get("Version", ""), p.get("License", "")] for p in display[:100]]
                out.table(
                    title=f"Package Licenses ({len(display)} of {len(data)})",
                    columns=[("Package", "bold"), ("Version", ""), ("License", "")],
                    rows=rows,
                    data_for_json=display,
                )
                if allowed_list and flagged:
                    out.warn(f"{len(flagged)} packages with non-allowed licenses.")
                    raise typer.Exit(1)
                return
            except Exception:
                pass

    # Fall back: parse from uv pip list
    out.info("pip-licenses not installed. Install: uv add --dev pip-licenses")
    result = _run_uv(["pip", "show", "--format", "columns"], cwd=str(root))
    if result.stdout:
        out.text(result.stdout[:3000])


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------
@app.command()
def graph(ctx: typer.Context) -> None:
    """Show the dependency graph via uv tree."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    out.info("Generating dependency graph ...")

    result = _run_uv(["tree", "--all-packages"], cwd=str(root))
    if result.returncode != 0:
        # Try without --all-packages
        result = _run_uv(["tree"], cwd=str(root))

    if result.stdout:
        typer.echo(result.stdout)
    if result.stderr and result.returncode != 0:
        out.error(result.stderr.strip())
        raise typer.Exit(result.returncode)


# ---------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------
@app.command()
def size(
    ctx: typer.Context,
    top: Annotated[int, typer.Option("--top", "-n", help="Show top N packages by size.")] = 20,
) -> None:
    """Show installed package sizes."""
    actx: AppContext = ctx.obj
    out = actx.output

    import os

    out.info(f"Analyzing package sizes (top {top}) ...")

    # Get site-packages directory
    try:
        import site

        site_dirs = site.getsitepackages()
    except Exception:
        site_dirs = []

    result = _run_uv(["pip", "list", "--format", "json"])
    packages: list[dict] = []
    if result.returncode == 0:
        import json

        try:
            pkg_list = json.loads(result.stdout)
        except Exception:
            pkg_list = []

        for site_dir in site_dirs:
            if not os.path.isdir(site_dir):
                continue
            for pkg_info in pkg_list:
                pkg_name = pkg_info.get("name", "")
                # Estimate size from dist-info directory
                dist_name = pkg_name.replace("-", "_")
                size_bytes = 0
                for entry in os.scandir(site_dir):
                    if entry.name.lower().startswith(dist_name.lower()):
                        try:
                            for root_dir, _dirs, files in os.walk(entry.path):
                                size_bytes += sum(
                                    os.path.getsize(os.path.join(root_dir, f))
                                    for f in files
                                    if not os.path.islink(os.path.join(root_dir, f))
                                )
                        except Exception:
                            pass
                if size_bytes > 0:
                    packages.append(
                        {
                            "name": pkg_name,
                            "version": pkg_info.get("version", ""),
                            "size_bytes": size_bytes,
                            "size_kb": round(size_bytes / 1024),
                        }
                    )
            break  # Only use first site dir

    if not packages:
        out.warn(
            "Could not determine package sizes. "
            "Try: du -sh $(python -c 'import site; print(site.getsitepackages()[0])')"
        )
        return

    packages.sort(key=lambda x: -x["size_bytes"])
    display = packages[:top]

    rows = [[p["name"], p["version"], f"{p['size_kb']} KB"] for p in display]
    out.table(
        title=f"Top {top} Packages by Size",
        columns=[("Package", "bold"), ("Version", ""), ("Size", "")],
        rows=rows,
        data_for_json=display,
    )

    total_mb = round(sum(p["size_bytes"] for p in packages) / 1024 / 1024, 1)
    out.info(f"Total installed: ~{total_mb} MB ({len(packages)} packages)")
