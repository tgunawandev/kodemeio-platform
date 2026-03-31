"""Dependency management commands."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run, run_pnpm

app = typer.Typer(help="Dependency management and analysis.")


@app.command()
def outdated(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for root)")] = None,
) -> None:
    """Check for outdated dependencies."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        cwd = get_app_dir(root, app_name)
    else:
        cwd = root

    target = app_name or "monorepo root"
    out.info(f"Checking outdated deps in {target}...")

    try:
        run_pnpm(["outdated"], cwd=cwd, capture=False, timeout=60)
    except CommandError:
        # pnpm outdated exits non-zero when outdated deps exist — this is expected
        pass
    except Exception as e:
        out.error(f"Failed to check outdated deps: {e}")


@app.command()
def audit(ctx: typer.Context) -> None:
    """Run security audit on dependencies."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Running pnpm audit...")
    try:
        run_pnpm(["audit"], cwd=root, capture=False, timeout=120)
        out.success("No vulnerabilities found")
    except Exception:
        out.warn("Vulnerabilities detected (see above)")


@app.command()
def graph(ctx: typer.Context) -> None:
    """Show internal package dependency graph."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    nodes: list[dict] = []

    # Read each app's package.json to find @kodemeio/* deps
    for name in actx.app_names:
        pkg_file = get_app_dir(root, name) / "package.json"
        if not pkg_file.exists():
            continue

        pkg = json.loads(pkg_file.read_text())
        all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        kodemeio_deps = sorted(k for k in all_deps if k.startswith("@kodemeio/"))

        children = [{"name": dep} for dep in kodemeio_deps]
        nodes.append(
            {
                "name": f"[cyan]{name}[/cyan]",
                "info": f"{len(kodemeio_deps)} packages",
                "children": children,
            }
        )

    out.tree(
        "Package Dependency Graph",
        nodes,
        data_for_json=[{"app": n["name"], "deps": [c["name"] for c in n.get("children", [])]} for n in nodes],
    )


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all workspace packages."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []

    # Apps
    for name in actx.app_names:
        pkg_file = get_app_dir(root, name) / "package.json"
        if not pkg_file.exists():
            continue
        pkg = json.loads(pkg_file.read_text())
        rel_path = str(get_app_dir(root, name).relative_to(root))
        rows.append([pkg.get("name", ""), pkg.get("version", ""), "app", rel_path])

    # Packages
    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for pkg_dir in sorted(packages_dir.iterdir()):
            pkg_file = pkg_dir / "package.json"
            if not pkg_file.exists():
                continue
            pkg = json.loads(pkg_file.read_text())
            rows.append([pkg.get("name", ""), pkg.get("version", ""), "package", f"packages/{pkg_dir.name}"])

    out.table(
        "Workspace Packages",
        [("Package", "cyan"), ("Version", "green"), ("Type", ""), ("Path", "dim")],
        rows,
    )


@app.command()
def why(
    ctx: typer.Context,
    package: Annotated[str, typer.Argument(help="Package name (e.g. @tanstack/react-query)")],
) -> None:
    """Show which apps depend on a specific package."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        pkg_file = get_app_dir(root, name) / "package.json"
        if not pkg_file.exists():
            continue
        pkg = json.loads(pkg_file.read_text())
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})

        if package in deps:
            rows.append([name, deps[package], "dependency"])
            json_data.append({"app": name, "version": deps[package], "type": "dependency"})
        elif package in dev_deps:
            rows.append([name, dev_deps[package], "devDependency"])
            json_data.append({"app": name, "version": dev_deps[package], "type": "devDependency"})

    # Also check shared packages
    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for pkg_dir in sorted(packages_dir.iterdir()):
            pkg_file = pkg_dir / "package.json"
            if not pkg_file.exists():
                continue
            pkg = json.loads(pkg_file.read_text())
            deps = pkg.get("dependencies", {})
            dev_deps = pkg.get("devDependencies", {})
            pkg_name = pkg.get("name", pkg_dir.name)

            if package in deps:
                rows.append([pkg_name, deps[package], "dependency"])
                json_data.append({"package": pkg_name, "version": deps[package], "type": "dependency"})
            elif package in dev_deps:
                rows.append([pkg_name, dev_deps[package], "devDependency"])
                json_data.append({"package": pkg_name, "version": dev_deps[package], "type": "devDependency"})

    if not rows:
        out.info(f"No workspace package depends on {package}")
        return

    out.table(
        f"Who uses {package}?",
        [("Package", "cyan"), ("Version", "green"), ("Type", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def duplicates(ctx: typer.Context) -> None:
    """Find packages with inconsistent versions across workspaces."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    # Collect all deps from all package.json files
    versions: dict[str, dict[str, str]] = {}  # {dep: {workspace: version}}

    def _scan_pkg(pkg_file: Path, workspace_name: str) -> None:
        if not pkg_file.exists():
            return
        try:
            pkg = json.loads(pkg_file.read_text())
            for dep_type in ("dependencies", "devDependencies"):
                for dep, ver in pkg.get(dep_type, {}).items():
                    if dep.startswith("@kodemeio/") or ver.startswith("workspace:"):
                        continue
                    if dep not in versions:
                        versions[dep] = {}
                    versions[dep][workspace_name] = ver
        except Exception:
            pass

    for name in actx.app_names:
        _scan_pkg(get_app_dir(root, name) / "package.json", name)

    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for pkg_dir in sorted(packages_dir.iterdir()):
            _scan_pkg(pkg_dir / "package.json", f"pkg:{pkg_dir.name}")

    # Find duplicates (same dep, different versions)
    rows: list[list[str]] = []
    json_data: list[dict] = []

    for dep, workspaces in sorted(versions.items()):
        unique_versions = set(workspaces.values())
        if len(unique_versions) <= 1:
            continue  # All same version
        for workspace, ver in sorted(workspaces.items()):
            rows.append([dep, workspace, ver])
        json_data.append({"package": dep, "versions": workspaces})

    if not rows:
        out.success("No version inconsistencies found")
        return

    out.table(
        "Version Inconsistencies",
        [("Package", "cyan"), ("Workspace", ""), ("Version", "yellow")],
        rows,
        data_for_json=json_data,
    )
    out.warn(f"{len(json_data)} package(s) have inconsistent versions")


@app.command("size")
def node_modules_size(ctx: typer.Context) -> None:
    """Show node_modules disk usage."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    nm = root / "node_modules"
    if not nm.is_dir():
        out.warn("node_modules not found — run `pnpm install`")
        return

    out.info("Calculating node_modules size (may take a moment)...")

    try:
        result = run(
            ["du", "-sh", str(nm)],
            cwd=root,
            capture=True,
            timeout=30,
        )
        size = result.stdout.strip().split("\t")[0]
        out.success(f"node_modules: {size}")
    except Exception:
        # Fallback: count in Python
        total = 0
        for f in nm.rglob("*"):
            if f.is_file():
                with contextlib.suppress(OSError):
                    total += f.stat().st_size
        from kctl_react.commands.build import _format_size

        out.success(f"node_modules: {_format_size(total)}")

    if out.json_mode:
        out.raw_json({"path": str(nm)})


_DEP_CATEGORIES: dict[str, str] = {
    # Core framework
    "react": "framework",
    "react-dom": "framework",
    "react-router-dom": "routing",
    "typescript": "language",
    # Build tools
    "vite": "build",
    "@vitejs/plugin-react": "build",
    "vite-plugin-pwa": "build",
    "tailwindcss": "styling",
    "@tailwindcss/vite": "styling",
    # State & data
    "@tanstack/react-query": "state",
    "@tanstack/react-table": "data-table",
    "zustand": "state",
    "idb": "offline",
    # UI
    "shadcn": "ui",
    "lucide-react": "icons",
    "sonner": "notifications",
    "class-variance-authority": "ui",
    "clsx": "ui",
    "tailwind-merge": "ui",
    "cmdk": "ui",
    "tw-animate-css": "ui",
    "echarts": "charts",
    "echarts-for-react": "charts",
    # Forms
    "react-hook-form": "forms",
    "zod": "validation",
    "@hookform/resolvers": "forms",
    # i18n
    "i18next": "i18n",
    "react-i18next": "i18n",
    # Maps & GPS
    "leaflet": "maps",
    "react-leaflet": "maps",
    # Auth & security
    "dompurify": "security",
    # Date
    "date-fns": "date",
    "react-day-picker": "date",
    # Mobile
    "@capacitor/core": "mobile",
    "@capacitor/android": "mobile",
    "@capacitor/cli": "mobile",
    "@capacitor/app": "mobile",
    "@capacitor/geolocation": "mobile",
    "@capacitor/keyboard": "mobile",
    "@capacitor/splash-screen": "mobile",
    "@capacitor/status-bar": "mobile",
    # Monitoring
    "@sentry/react": "monitoring",
    "@sentry/vite-plugin": "monitoring",
    # Codegen
    "@hey-api/openapi-ts": "codegen",
    "@hey-api/client-fetch": "codegen",
    # Notifications
    "firebase": "push-notifications",
    # Export
    "xlsx": "export",
    "html2canvas": "export",
    # QR
    "html5-qrcode": "qr",
    "qrcode-generator": "qr",
    "qrcode.react": "qr",
    # Testing
    "@testing-library/react": "testing",
    # PWA
    "workbox-window": "pwa",
}


def _categorize_dep(name: str) -> str:
    """Return the category for a dependency name."""
    if name in _DEP_CATEGORIES:
        return _DEP_CATEGORIES[name]
    if name.startswith("@radix-ui/"):
        return "ui-primitives"
    if name.startswith("@types/"):
        return "types"
    return "other"


def _collect_all_external_deps(root: Path, app_names: list[str], packages: list[str]) -> dict[str, dict[str, str]]:
    """Collect ALL external dependencies across all workspaces.

    Returns {dep_name: {workspace_name: version_string}}.
    Skips @kodemeio/* and workspace:* versions.
    """
    versions: dict[str, dict[str, str]] = {}

    def _scan(pkg_file: Path, workspace: str) -> None:
        if not pkg_file.exists():
            return
        try:
            pkg = json.loads(pkg_file.read_text())
        except Exception:
            return
        for dep_type in ("dependencies", "devDependencies"):
            for dep, ver in pkg.get(dep_type, {}).items():
                if dep.startswith("@kodemeio/"):
                    continue
                if ver.startswith("workspace:"):
                    continue
                if dep not in versions:
                    versions[dep] = {}
                versions[dep][workspace] = ver

    for name in app_names:
        _scan(get_app_dir(root, name) / "package.json", name)

    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for pkg_name in packages:
            _scan(packages_dir / pkg_name / "package.json", f"pkg:{pkg_name}")

    return versions


def _semver_key(ver: str) -> list[int]:
    """Parse a semver-ish string into a sortable list of ints."""
    clean = ver.lstrip("^~>=<")
    parts = clean.split(".")
    result: list[int] = []
    for p in parts[:3]:
        try:
            result.append(int(p.split("-")[0]))
        except ValueError:
            result.append(0)
    return result


@app.command("upgrade")
def upgrade(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", help="Only upgrade deps in this category")] = None,
    major: Annotated[bool, typer.Option("--major", help="Include major version bumps")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change")] = False,
) -> None:
    """Smart dependency upgrade — show outdated deps with context and apply upgrades.

    Scans all external deps, checks for newer versions via `pnpm outdated --json`,
    and shows a categorized upgrade plan. Use --dry-run to preview.

    Examples:
      kctl-react deps upgrade                  # Show upgrade plan
      kctl-react deps upgrade --category build # Only build tools
      kctl-react deps upgrade --major          # Include major bumps
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Checking for outdated dependencies...")

    # Run pnpm outdated --json to get available updates
    try:
        result = run_pnpm(["outdated", "--json"], cwd=root, capture=True, timeout=120)
        raw = result.stdout
    except CommandError as e:
        # pnpm outdated exits non-zero when outdated deps exist — parse stderr/stdout
        raw = e.stderr or ""
        if not raw:
            # Try to get stdout from the exception detail
            raw = str(e)

    # Parse JSON output — pnpm outdated --json format varies by version
    outdated: dict[str, dict] = {}
    try:
        data = json.loads(raw)
        # pnpm v9 format: dict of {pkg_name: {current, latest, wanted, ...}}
        if isinstance(data, dict):
            for pkg_name, info in data.items():
                if isinstance(info, dict) and "current" in info:
                    outdated[pkg_name] = info
    except (json.JSONDecodeError, ValueError):
        pass

    if not outdated:
        # Fallback: use our own dep inventory to show all deps with versions
        out.info("Could not parse pnpm outdated output — showing dep inventory instead")
        all_deps = _collect_all_external_deps(root, actx.app_names, actx.packages)
        rows: list[list[str]] = []
        json_data: list[dict] = []
        for dep_name in sorted(all_deps):
            cat = _categorize_dep(dep_name)
            if category and cat != category:
                continue
            versions = sorted(set(all_deps[dep_name].values()))
            rows.append([dep_name, ", ".join(versions), cat, str(len(all_deps[dep_name]))])
            json_data.append({"package": dep_name, "versions": versions, "category": cat})
        out.table(
            "Dependencies (run `pnpm outdated` manually for update info)",
            [("Package", "cyan"), ("Current", "green"), ("Category", ""), ("Used By", "dim")],
            rows,
            data_for_json=json_data,
        )
        return

    # Build upgrade plan
    rows = []
    json_data = []
    minor_count = 0
    major_count = 0

    for pkg_name in sorted(outdated):
        info = outdated[pkg_name]
        current = info.get("current", "?")
        wanted = info.get("wanted", current)
        latest = info.get("latest", current)
        cat = _categorize_dep(pkg_name)

        if category and cat != category:
            continue

        # Determine if this is a major bump
        current_major = _semver_key(current)[0] if current != "?" else 0
        latest_major = _semver_key(latest)[0]
        is_major = latest_major > current_major

        if is_major:
            major_count += 1
            if not major:
                continue  # Skip major bumps unless --major flag
            bump_type = "[red]MAJOR[/red]"
        else:
            minor_count += 1
            bump_type = "[green]minor[/green]" if wanted != current else "[dim]patch[/dim]"

        rows.append([pkg_name, current, wanted, latest, cat, bump_type])
        json_data.append(
            {
                "package": pkg_name,
                "current": current,
                "wanted": wanted,
                "latest": latest,
                "category": cat,
                "major": is_major,
            }
        )

    if not rows:
        out.success("All dependencies are up to date" + (f" (category: {category})" if category else ""))
        if major_count > 0:
            out.info(f"{major_count} major upgrade(s) available — use --major to include")
        return

    out.table(
        f"Upgrade Plan ({len(rows)} packages)",
        [
            ("Package", "cyan"),
            ("Current", "dim"),
            ("Wanted", "green"),
            ("Latest", "yellow"),
            ("Category", ""),
            ("Type", ""),
        ],
        rows,
        data_for_json=json_data,
    )

    if major_count > 0 and not major:
        out.info(f"{major_count} major upgrade(s) hidden — use --major to include")

    if dry_run:
        out.info("[dry-run] No changes applied")
        return

    # Apply upgrades
    out.info("Applying upgrades via pnpm update...")
    try:
        cmd = ["update"]
        if not major:
            cmd.append("--no-save")  # Only update within semver range
        run_pnpm(cmd, cwd=root, capture=False, timeout=300)
        out.success(f"Upgraded {len(rows)} package(s)")
    except CommandError as exc:
        out.error(f"Upgrade failed: {exc}")
        raise typer.Exit(1) from exc


@app.command("stack")
def stack(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", help="Filter by category")] = None,
) -> None:
    """Show full external dependency inventory across the monorepo."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Scanning all external dependencies...")

    all_deps = _collect_all_external_deps(root, actx.app_names, actx.packages)

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for dep_name in sorted(all_deps):
        workspaces = all_deps[dep_name]
        cat = _categorize_dep(dep_name)

        if category and cat != category:
            continue

        unique_versions = sorted(set(workspaces.values()))
        version_str = ", ".join(unique_versions)
        used_by = len(workspaces)
        status = "ok" if len(unique_versions) == 1 else "inconsistent"

        rows.append([dep_name, version_str, cat, str(used_by), status])
        json_data.append(
            {
                "package": dep_name,
                "versions": unique_versions,
                "category": cat,
                "used_by": used_by,
                "status": status,
                "workspaces": workspaces,
            }
        )

    if not rows:
        out.info("No external dependencies found" + (f" in category '{category}'" if category else ""))
        if out.json_mode:
            out.raw_json([])
        return

    out.table(
        "External Dependency Inventory",
        [
            ("Package", "cyan"),
            ("Version(s)", "green"),
            ("Category", ""),
            ("Used By", ""),
            ("Status", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )
    out.info(f"{len(rows)} external dependencies found")


@app.command("health")
def health(ctx: typer.Context) -> None:
    """Run dependency health checks and produce an overall score."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Running dependency health checks...")

    all_deps = _collect_all_external_deps(root, actx.app_names, actx.packages)
    total_deps = len(all_deps)

    # Check 1: Version inconsistencies
    inconsistent_count = 0
    for workspaces in all_deps.values():
        if len(set(workspaces.values())) > 1:
            inconsistent_count += 1

    # Check 2: Lockfile exists and is committed
    lockfile = root / "pnpm-lock.yaml"
    lockfile_exists = lockfile.exists()
    lockfile_committed = False
    if lockfile_exists:
        try:
            result = run(
                ["git", "ls-files", "--error-unmatch", "pnpm-lock.yaml"],
                cwd=root,
                capture=True,
                timeout=10,
            )
            lockfile_committed = result.returncode == 0
        except Exception:
            lockfile_committed = False

    # Build checks table
    checks: list[dict] = [
        {
            "check": "Version consistency",
            "status": "pass" if inconsistent_count == 0 else "fail",
            "detail": f"{inconsistent_count} inconsistencies across {total_deps} deps",
        },
        {
            "check": "Lockfile exists",
            "status": "pass" if lockfile_exists else "fail",
            "detail": "pnpm-lock.yaml present" if lockfile_exists else "pnpm-lock.yaml missing",
        },
        {
            "check": "Lockfile committed",
            "status": "pass" if lockfile_committed else "fail",
            "detail": "Tracked in git" if lockfile_committed else "Not tracked in git",
        },
    ]

    # Calculate score
    passed = sum(1 for c in checks if c["status"] == "pass")
    total_checks = len(checks)
    score = int(passed / total_checks * 100)

    rows = [[c["check"], c["status"], c["detail"]] for c in checks]
    rows.append(["Overall score", f"{score}%", f"{passed}/{total_checks} checks passed"])

    out.table(
        "Dependency Health",
        [("Check", "cyan"), ("Status", "green"), ("Detail", "dim")],
        rows,
        data_for_json={"checks": checks, "score": score, "total_deps": total_deps},
    )

    if score == 100:
        out.success(f"Dependency health: {score}%")
    else:
        out.warn(f"Dependency health: {score}%")


@app.command("sync")
def sync(
    ctx: typer.Context,
    fix: Annotated[bool, typer.Option("--fix", help="Update all to highest version and run pnpm install")] = False,
) -> None:
    """Check and fix version inconsistencies across ALL external dependencies."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Scanning dependency versions...")

    versions = _collect_all_external_deps(root, actx.app_names, actx.packages)

    rows: list[list[str]] = []
    json_data: list[dict] = []
    inconsistent: dict[str, dict[str, str]] = {}

    for dep in sorted(versions):
        workspaces = versions[dep]
        unique_versions = set(workspaces.values())
        if len(unique_versions) <= 1:
            continue

        inconsistent[dep] = workspaces
        version_list = ", ".join(f"{v} ({w})" for w, v in sorted(workspaces.items()))
        rows.append([dep, str(len(unique_versions)), version_list])
        json_data.append(
            {
                "package": dep,
                "version_count": len(unique_versions),
                "workspaces": workspaces,
            }
        )

    if not inconsistent:
        out.success("All external dependencies are in sync")
        if out.json_mode:
            out.raw_json({"inconsistencies": [], "total": 0})
        return

    out.table(
        "Version Inconsistencies",
        [("Package", "cyan"), ("Versions", "yellow"), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )
    out.warn(f"{len(inconsistent)} package(s) have inconsistent versions")

    if not fix:
        return

    out.info("Fixing version inconsistencies...")
    for dep, workspaces in inconsistent.items():
        highest_ver = max(workspaces.values(), key=_semver_key)
        out.info(f"  {dep}: -> {highest_ver}")

        for workspace in workspaces:
            if workspace.startswith("pkg:"):
                pkg_name = workspace[4:]
                pkg_file = root / "packages" / pkg_name / "package.json"
            else:
                pkg_file = get_app_dir(root, workspace) / "package.json"

            if not pkg_file.exists():
                continue

            try:
                pkg = json.loads(pkg_file.read_text())
                changed = False
                for dep_type in ("dependencies", "devDependencies"):
                    if dep in pkg.get(dep_type, {}):
                        pkg[dep_type][dep] = highest_ver
                        changed = True
                if changed:
                    pkg_file.write_text(json.dumps(pkg, indent=2) + "\n")
            except Exception as e:
                out.warn(f"  Could not update {pkg_file}: {e}")

    out.info("Running pnpm install...")
    try:
        run_pnpm(["install"], cwd=root, capture=False, timeout=120)
        out.success("Dependencies synced and installed")
    except Exception as e:
        out.error(f"pnpm install failed: {e}")
        raise typer.Exit(1) from None
