"""Git utilities for change detection and affected app analysis."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kctl_react.core.discovery import discover_apps, discover_packages


def get_changed_files(root: Path, base: str = "HEAD~1") -> list[str]:
    """Get list of files changed since base ref."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Try against main if HEAD~1 fails (first commit)
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
        return [f for f in result.stdout.strip().splitlines() if f]
    except Exception:
        return []


def get_uncommitted_files(root: Path) -> list[str]:
    """Get list of uncommitted (staged + unstaged) files."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--no-renames"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = []
        for line in result.stdout.strip().splitlines():
            if line and len(line) > 3:
                files.append(line[3:].strip())
        return files
    except Exception:
        return []


def get_affected_apps(root: Path, base: str = "HEAD~1") -> list[str]:
    """Determine which apps are affected by changes since base ref.

    Rules:
    - apps/{name}/* changed → that app is affected
    - packages/{name}/* changed → all apps using that package are affected
    - Root config changed (turbo.json, package.json, tsconfig) → all apps
    """
    changed = get_changed_files(root, base) + get_uncommitted_files(root)
    if not changed:
        return []

    app_registry = discover_apps(root)
    valid_apps = list(app_registry.keys())
    package_list = discover_packages(root)

    affected: set[str] = set()
    changed_packages: set[str] = set()

    root_config_files = {
        "turbo.json",
        "package.json",
        "tsconfig.json",
        "tsconfig.base.json",
        "pnpm-lock.yaml",
    }

    for filepath in changed:
        parts = filepath.split("/")

        # Root config change → all apps affected
        if filepath in root_config_files:
            return valid_apps

        # Direct app change
        if len(parts) >= 2 and parts[0] == "apps" and parts[1] in app_registry:
            affected.add(parts[1])

        # Package change
        if len(parts) >= 2 and parts[0] == "packages" and parts[1] in package_list:
            changed_packages.add(parts[1])

    # Resolve package → app dependencies
    if changed_packages:
        import json

        for app_name in valid_apps:
            pkg_file = root / "apps" / app_name / "package.json"
            if not pkg_file.exists():
                continue
            try:
                pkg = json.loads(pkg_file.read_text())
                all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for changed_pkg in changed_packages:
                    if f"@kodemeio/{changed_pkg}" in all_deps:
                        affected.add(app_name)
            except Exception:
                continue

    return sorted(affected)


def get_current_branch(root: Path) -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_last_commit_hash(root: Path) -> str:
    """Get short hash of last commit."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""
