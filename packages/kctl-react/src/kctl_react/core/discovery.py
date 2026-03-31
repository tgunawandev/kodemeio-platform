"""Auto-discover apps and packages from the monorepo filesystem.

Scans apps/ and packages/ directories, reads package.json files,
and extracts metadata (name, version, port, description).
Works with any Turbo + pnpm monorepo, not just Kodemeio.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _extract_port(dev_script: str) -> int:
    """Extract port number from a vite dev script like 'vite --port 4004'."""
    match = re.search(r"--port\s+(\d+)", dev_script)
    if match:
        return int(match.group(1))
    # Try PORT= env var pattern
    match = re.search(r"PORT=(\d+)", dev_script)
    if match:
        return int(match.group(1))
    return 0


def detect_framework(app_dir: Path) -> str:
    """Detect whether an app uses Vite or Next.js.

    Returns 'nextjs' if next.config.ts/js/mjs exists, otherwise 'vite'.
    """
    for name in ("next.config.ts", "next.config.js", "next.config.mjs"):
        if (app_dir / name).exists():
            return "nextjs"
    return "vite"


def _read_pkg_json(path: Path) -> dict:
    """Safely read and parse a package.json file."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


APP_TYPE_DIRS = ("spa", "web", "api")


def discover_apps(root: Path) -> dict[str, dict[str, Any]]:
    """Discover apps from the apps/ directory.

    Scans apps/{spa,web,api}/ subdirectories for nested app structure.
    Falls back to flat apps/ scanning for legacy repos.

    Returns a dict like:
      {"sfa": {"port": 4004, "name": "Sales Force Automation", "package": "@kodemeio/sfa", "type": "spa", "path": Path(...)}}

    Works with any Turbo monorepo — reads package.json for metadata.
    """
    apps_dir = root / "apps"
    if not apps_dir.is_dir():
        return {}

    registry: dict[str, dict[str, Any]] = {}

    # Try nested structure first: apps/{spa,web,api}/{app}
    found_nested = False
    for type_name in APP_TYPE_DIRS:
        type_dir = apps_dir / type_name
        if not type_dir.is_dir():
            continue

        found_nested = True
        for app_dir in sorted(type_dir.iterdir()):
            if not app_dir.is_dir():
                continue

            pkg_file = app_dir / "package.json"
            if not pkg_file.exists():
                continue

            pkg = _read_pkg_json(pkg_file)
            if not pkg:
                continue

            dev_script = pkg.get("scripts", {}).get("dev", "")
            port = _extract_port(dev_script)
            pkg_name = pkg.get("name", app_dir.name)
            description = pkg.get("description", "")

            registry[app_dir.name] = {
                "port": port,
                "name": description or app_dir.name,
                "package": pkg_name,
                "framework": detect_framework(app_dir),
                "type": type_name,
                "path": app_dir,
            }

    if found_nested:
        return registry

    # Legacy fallback: flat apps/{app} structure
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue

        pkg_file = app_dir / "package.json"
        if not pkg_file.exists():
            continue

        pkg = _read_pkg_json(pkg_file)
        if not pkg:
            continue

        dev_script = pkg.get("scripts", {}).get("dev", "")
        port = _extract_port(dev_script)
        pkg_name = pkg.get("name", app_dir.name)
        description = pkg.get("description", "")

        registry[app_dir.name] = {
            "port": port,
            "name": description or app_dir.name,
            "package": pkg_name,
            "framework": detect_framework(app_dir),
            "type": "spa",
            "path": app_dir,
        }

    return registry


def get_app_dir(root: Path, app_name: str, registry: dict[str, dict[str, Any]] | None = None) -> Path:
    """Get the filesystem path for an app, using registry or fallback scanning."""
    if registry and app_name in registry:
        return registry[app_name]["path"]
    # Fallback: scan for it
    for type_name in APP_TYPE_DIRS:
        candidate = root / "apps" / type_name / app_name
        if candidate.is_dir():
            return candidate
    # Legacy fallback for backwards compat
    return root / "apps" / app_name


def discover_packages(root: Path) -> list[str]:
    """Discover shared packages from the packages/ directory.

    Returns a list of package directory names: ["core", "ui", "tailwind-config", ...]
    """
    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        return []

    result: list[str] = []
    for pkg_dir in sorted(packages_dir.iterdir()):
        if not pkg_dir.is_dir():
            continue
        if (pkg_dir / "package.json").exists():
            result.append(pkg_dir.name)

    return result


def get_monorepo_scope(root: Path) -> str:
    """Detect the npm scope (e.g. '@kodemeio' or '@kontenos') from root package.json.

    Falls back to reading the first app's package name.
    """
    # Try root package.json
    root_pkg = _read_pkg_json(root / "package.json")
    root_name = root_pkg.get("name", "")
    if root_name.startswith("@"):
        return root_name.split("/")[0]

    # Try first app
    apps = discover_apps(root)
    for info in apps.values():
        pkg_name = info.get("package", "")
        if pkg_name.startswith("@"):
            return pkg_name.split("/")[0]

    # Try pnpm-workspace.yaml for name hints
    return ""
