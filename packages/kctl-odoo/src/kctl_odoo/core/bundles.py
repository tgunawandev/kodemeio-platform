"""Bundle and profile YAML parser for the Kodemeio module installation system.

Replicates the exact parsing logic from bin/mod (parse_bundle_yaml) and
bin/install-profiles (_parse_profile_bundles / _resolve_modules) so that
kctl-odoo can work with bundles without requiring Docker or shell scripts.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# ============================================================================
# Data Models
# ============================================================================


class BundleGroup(BaseModel):
    """A named group within a bundle."""

    description: str = ""
    depends: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)


class Bundle(BaseModel):
    """A parsed bundle YAML file."""

    name: str = ""
    description: str = ""
    requires: list[str] = Field(default_factory=list)
    groups: dict[str, BundleGroup] = Field(default_factory=dict)
    default: list[str] = Field(default_factory=list)
    # Set when loaded from a simple list format (no groups)
    flat_modules: list[str] = Field(default_factory=list)
    # Source file path
    source: Path | None = None

    @property
    def is_flat(self) -> bool:
        """True if this bundle is a simple module list with no groups."""
        return bool(self.flat_modules) and not self.groups

    @property
    def total_modules(self) -> int:
        if self.is_flat:
            return len(self.flat_modules)
        seen: set[str] = set()
        for g in self.groups.values():
            for m in g.modules:
                seen.add(m)
        return len(seen)


class Profile(BaseModel):
    """A parsed deployment profile YAML file."""

    name: str = ""
    description: str = ""
    bundles: list[str] = Field(default_factory=list)
    extends: str = ""  # Parent profile name (e.g., "profile-distribution")
    source: Path | None = None


# ============================================================================
# Parsing
# ============================================================================


def load_bundle(path: Path) -> Bundle:
    """Load and parse a bundle YAML file.

    Handles both formats:
    - Simple list: [mod1, mod2, ...]
    - Full format: {name, description, groups: {g1: {modules: [...], depends: [...]}}, default: [...]}
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return Bundle(name=path.stem, source=path)

    # Simple list format (backward compatible)
    if isinstance(data, list):
        return Bundle(
            name=path.stem,
            flat_modules=[str(m) for m in data],
            source=path,
        )

    # Full YAML format with groups
    groups: dict[str, BundleGroup] = {}
    raw_groups = data.get("groups", {})
    for gname, gdata in raw_groups.items():
        if isinstance(gdata, dict):
            groups[gname] = BundleGroup(
                description=gdata.get("description", ""),
                depends=gdata.get("depends", []),
                modules=gdata.get("modules", []),
            )

    default = data.get("default", list(raw_groups.keys()))

    return Bundle(
        name=data.get("name", path.stem),
        description=data.get("description", ""),
        requires=data.get("requires", []),
        groups=groups,
        default=default,
        source=path,
    )


def resolve_modules(bundle: Bundle, groups: list[str] | None = None) -> list[str]:
    """Resolve a bundle to an ordered, deduplicated list of module names.

    Exactly matches bin/mod parse_bundle_yaml logic:
    - None/empty groups → use bundle.default
    - ["all"] → use all groups
    - ["g1", "g2"] → use specified groups
    - Dependencies resolved recursively before group modules
    - Deduplication preserves first-seen order
    """
    if bundle.is_flat:
        return list(bundle.flat_modules)

    # Determine requested groups
    if groups and len(groups) == 1 and groups[0].strip().lower() == "all":
        requested = list(bundle.groups.keys())
    elif groups:
        requested = [g.strip() for g in groups if g.strip()]
    else:
        requested = list(bundle.default)

    # Resolve with dependency order
    resolved: set[str] = set()
    modules: list[str] = []

    def _resolve_group(gname: str) -> None:
        if gname in resolved:
            return
        if gname not in bundle.groups:
            return

        group = bundle.groups[gname]

        # Resolve dependencies first
        for dep in group.depends:
            _resolve_group(dep)

        resolved.add(gname)

        # Add modules (deduplicated)
        for mod in group.modules:
            if mod not in modules:
                modules.append(mod)

    for gname in requested:
        _resolve_group(gname)

    return modules


def load_profile(path: Path) -> Profile:
    """Load and parse a deployment profile YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return Profile(name=path.stem, source=path)

    return Profile(
        name=data.get("name", path.stem),
        description=data.get("description", ""),
        bundles=data.get("bundles", []),
        extends=data.get("extends", ""),
        source=path,
    )


def resolve_profile_modules(profile: Profile, install_dir: Path) -> list[str]:
    """Resolve all modules in a profile across all its bundles.

    Supports:
    - bundle:group1,group2 syntax from install-profiles
    - extends: parent-profile inheritance (AI profiles)
    Deduplicates across bundles preserving first-seen order.
    """
    all_modules: list[str] = []

    # If this profile extends another, resolve parent first
    if profile.extends:
        parent_path = _find_profile_file(install_dir, profile.extends)
        if parent_path:
            parent = load_profile(parent_path)
            parent_modules = resolve_profile_modules(parent, install_dir)
            for mod in parent_modules:
                if mod not in all_modules:
                    all_modules.append(mod)

    for entry in profile.bundles:
        # Parse bundle:groups syntax
        bundle_name, groups = _parse_bundle_entry(entry)

        # Find the bundle file
        bundle_path = _find_bundle_file(install_dir, bundle_name)
        if bundle_path is None:
            continue

        bundle = load_bundle(bundle_path)
        modules = resolve_modules(bundle, groups)

        # Deduplicate across bundles
        for mod in modules:
            if mod not in all_modules:
                all_modules.append(mod)

    return all_modules


# ============================================================================
# Discovery
# ============================================================================


def discover_bundles(install_dir: Path) -> list[Bundle]:
    """Discover all bundle YAML files in a directory (excludes profiles)."""
    bundles: list[Bundle] = []
    for path in sorted(install_dir.glob("*.yaml")):
        if path.name.startswith("profile-"):
            continue
        try:
            bundles.append(load_bundle(path))
        except Exception:
            continue
    return bundles


def discover_profiles(install_dir: Path) -> list[Profile]:
    """Discover all profile YAML files in a directory."""
    profiles: list[Profile] = []
    for path in sorted(install_dir.glob("profile-*.yaml")):
        try:
            profiles.append(load_profile(path))
        except Exception:
            continue
    return profiles


# ============================================================================
# Helpers
# ============================================================================


def _find_profile_file(install_dir: Path, name: str) -> Path | None:
    """Find a profile YAML file by name in the install directory."""
    for prefix in ("profile-", ""):
        for ext in (".yaml", ".yml"):
            path = install_dir / f"{prefix}{name}{ext}"
            if path.exists():
                return path
    return None


def _parse_bundle_entry(entry: str) -> tuple[str, list[str] | None]:
    """Parse a profile bundle entry like 'private-retail:analytics' into (name, groups)."""
    if ":" in entry:
        parts = entry.split(":", 1)
        name = parts[0].strip()
        groups = [g.strip() for g in parts[1].split(",") if g.strip()]
        return name, groups
    return entry.strip(), None


def _find_bundle_file(install_dir: Path, name: str) -> Path | None:
    """Find a bundle YAML file by name in the install directory."""
    # Try exact name
    for ext in (".yaml", ".yml"):
        path = install_dir / f"{name}{ext}"
        if path.exists():
            return path
    return None


def get_default_install_dir() -> Path:
    """Resolve the install directory with fallback strategies.

    1. ``KCTL_ODOO_REPO`` environment variable
    2. Walk up from CWD looking for an ``install/`` directory
    3. Config profile ``project_root`` setting
    4. Fall back to ``./install`` (original behaviour)
    """
    import os

    # 1. Explicit env var
    repo = os.environ.get("KCTL_ODOO_REPO")
    if repo:
        candidate = Path(repo) / "install"
        if candidate.is_dir():
            return candidate

    # 2. Walk up from CWD
    cur = Path.cwd()
    for _ in range(10):  # avoid infinite walk
        candidate = cur / "install"
        if candidate.is_dir():
            return candidate
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    # 3. Config profile project_root
    try:
        from kctl_odoo.core.config import get_project_root_from_config

        config_root = get_project_root_from_config()
        if config_root is not None:
            candidate = config_root / "install"
            if candidate.is_dir():
                return candidate
    except Exception:
        pass

    # 4. Original fallback
    return Path.cwd() / "install"
