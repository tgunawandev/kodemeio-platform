"""Addon discovery and health scoring for the Kodemeio Odoo platform.

Provides:
- ``Addon`` — Pydantic model representing a discovered Odoo addon
- ``HealthResult`` — Pydantic model for score_health() output
- ``discover_addons()`` — Scan filesystem paths for addons
- ``get_default_addon_paths()`` — Resolve standard src/ paths from repo root
- ``get_addon_path_labels()`` — Map paths to source type labels
- ``score_health()`` — Score an addon 0-100 across 12 quality checks
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

# ============================================================================
# Data Models
# ============================================================================

# Weights for each of the 12 health checks (must sum to 100)
_CHECK_WEIGHTS: dict[str, int] = {
    "manifest_exists": 10,
    "installable": 5,
    "version_set": 5,
    "description_set": 5,
    "author_set": 5,
    "license_set": 5,
    "depends_set": 5,
    "security_csv": 15,
    "tests_exist": 15,
    "claude_md": 10,
    "views_exist": 10,
    "model_descriptions": 10,
}

assert sum(_CHECK_WEIGHTS.values()) == 100, "Check weights must sum to 100"


class Addon(BaseModel):
    """A discovered Odoo addon module."""

    name: str
    path: Path
    source_type: str  # "private" | "oca" | "external"
    manifest: dict = Field(default_factory=dict)

    @property
    def version(self) -> str:
        """Module version from manifest, e.g. '18.0.1.0.0'."""
        return str(self.manifest.get("version", ""))

    @property
    def installable(self) -> bool:
        """True if manifest marks the module as installable (defaults to True)."""
        return bool(self.manifest.get("installable", True))

    @property
    def depends(self) -> list[str]:
        """List of module dependencies from manifest."""
        return list(self.manifest.get("depends", []))

    @property
    def summary(self) -> str:
        """Short summary from manifest."""
        return str(self.manifest.get("summary", ""))

    @property
    def author(self) -> str:
        """Author string from manifest."""
        return str(self.manifest.get("author", ""))

    @property
    def license(self) -> str:
        """License identifier from manifest."""
        return str(self.manifest.get("license", ""))


class HealthResult(BaseModel):
    """Result of score_health() for a single addon."""

    score: int
    checks: dict[str, bool] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


# ============================================================================
# Discovery
# ============================================================================


def discover_addons(
    addon_paths: list[Path],
    path_labels: dict[Path, str] | None = None,
) -> list[Addon]:
    """Scan directories for Odoo addon modules.

    A directory is considered an addon if it contains ``__manifest__.py``.
    Manifests are parsed safely using ``ast.literal_eval`` (Python literal
    parser — evaluates only data structures, not executable code).

    Args:
        addon_paths: Directories to scan (top-level; subdirs are the addons).
        path_labels: Optional mapping of path -> source_type label
                     (e.g. ``{Path("src/private"): "private"}``).
                     Defaults to ``"private"`` when not provided.

    Returns:
        List of discovered :class:`Addon` instances, sorted by name.
    """
    labels = path_labels or {}
    addons: list[Addon] = []

    for base_path in addon_paths:
        if not base_path.is_dir():
            continue

        source_type = labels.get(base_path, "private")

        for candidate in sorted(base_path.iterdir()):
            if not candidate.is_dir():
                continue

            manifest_file = candidate / "__manifest__.py"
            if not manifest_file.exists():
                continue

            manifest = _parse_manifest(manifest_file)
            if manifest is None:
                continue

            addons.append(
                Addon(
                    name=candidate.name,
                    path=candidate,
                    source_type=source_type,
                    manifest=manifest,
                )
            )

    return addons


def _parse_manifest(path: Path) -> dict | None:
    """Parse a __manifest__.py file using ast.literal_eval.

    ast.literal_eval is safe: it only evaluates Python literal structures
    (dicts, lists, strings, numbers, booleans) — no arbitrary code execution.

    Returns the manifest dict, or None if parsing fails.
    """
    try:
        content = path.read_text(encoding="utf-8")
        # ast.literal_eval is the safe standard for Odoo manifest parsing
        result = ast.literal_eval(content.strip())
        if isinstance(result, dict):
            return result
        return None
    except Exception:
        return None


# ============================================================================
# Path resolution helpers
# ============================================================================


def _find_repo_root() -> Path | None:
    """Locate the Odoo project root directory.

    Resolution order:
    1. ``KCTL_ODOO_REPO`` environment variable
    2. Walk up from CWD looking for a directory that contains both
       ``install/`` and ``src/`` subdirectories.

    Returns:
        Path to the repo root, or None if not found.
    """
    # 1. Explicit env var
    repo = os.environ.get("KCTL_ODOO_REPO")
    if repo:
        return Path(repo)

    # 2. Walk up from CWD
    cur = Path(os.getcwd())
    for _ in range(15):  # avoid infinite walk
        if (cur / "install").is_dir() and (cur / "src").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    return None


def get_default_addon_paths() -> list[Path]:
    """Return the standard addon source paths for the current project.

    Checks ``src/private``, ``src/oca``, and ``src/external`` under the
    resolved repo root.  Only paths that actually exist are returned.

    Returns:
        List of existing addon source directories.
    """
    root = _find_repo_root()
    if root is None:
        return []

    candidates = [
        root / "src" / "private",
        root / "src" / "oca",
        root / "src" / "external",
    ]
    return [p for p in candidates if p.is_dir()]


def get_addon_path_labels() -> dict[Path, str]:
    """Return a mapping of addon paths to their source-type labels.

    Maps each standard path to one of ``"private"``, ``"oca"``, or
    ``"external"``.

    Returns:
        Dict of ``{Path: source_type_str}`` for existing directories.
    """
    root = _find_repo_root()
    if root is None:
        return {}

    mapping: dict[Path, str] = {}
    src_labels = {
        "private": "private",
        "oca": "oca",
        "external": "external",
    }
    for subdir, label in src_labels.items():
        path = root / "src" / subdir
        if path.is_dir():
            mapping[path] = label

    return mapping


# ============================================================================
# Health scoring
# ============================================================================


def score_health(addon: Addon) -> HealthResult:
    """Score an addon's quality on a 0-100 scale across 12 checks.

    Checks and their weights:
    - ``manifest_exists``   (10): ``__manifest__.py`` file present on disk
    - ``installable``       (5):  manifest ``installable`` is True
    - ``version_set``       (5):  ``version`` field is non-empty
    - ``description_set``   (5):  ``description`` field is non-empty
    - ``author_set``        (5):  ``author`` field is non-empty
    - ``license_set``       (5):  ``license`` field is non-empty
    - ``depends_set``       (5):  ``depends`` list is non-empty
    - ``security_csv``      (15): ``security/ir.model.access.csv`` exists
    - ``tests_exist``       (15): ``tests/`` dir has at least one ``test_*.py``
    - ``claude_md``         (10): ``CLAUDE.md`` file present
    - ``views_exist``       (10): ``views/`` dir has at least one ``.xml``
    - ``model_descriptions``(10): all models with ``_name`` also have ``_description``

    Args:
        addon: Discovered :class:`Addon` to evaluate.

    Returns:
        :class:`HealthResult` with score, per-check bool dict, and issues list.
    """
    path = addon.path
    manifest = addon.manifest

    checks: dict[str, bool] = {}
    issues: list[str] = []

    # 1. manifest_exists
    checks["manifest_exists"] = (path / "__manifest__.py").exists()
    if not checks["manifest_exists"]:
        issues.append("Missing __manifest__.py")

    # 2. installable
    checks["installable"] = bool(manifest.get("installable", True))
    if not checks["installable"]:
        issues.append("installable is False in manifest")

    # 3. version_set
    version = str(manifest.get("version", ""))
    checks["version_set"] = bool(version)
    if not checks["version_set"]:
        issues.append("Missing version in manifest")

    # 4. description_set
    description = str(manifest.get("description", ""))
    checks["description_set"] = bool(description)
    if not checks["description_set"]:
        issues.append("Missing description in manifest")

    # 5. author_set
    author = str(manifest.get("author", ""))
    checks["author_set"] = bool(author)
    if not checks["author_set"]:
        issues.append("Missing author in manifest")

    # 6. license_set
    license_val = str(manifest.get("license", ""))
    checks["license_set"] = bool(license_val)
    if not checks["license_set"]:
        issues.append("Missing license in manifest")

    # 7. depends_set
    depends = manifest.get("depends", [])
    checks["depends_set"] = isinstance(depends, list) and len(depends) > 0
    if not checks["depends_set"]:
        issues.append("Missing or empty depends in manifest")

    # 8. security_csv
    csv_path = path / "security" / "ir.model.access.csv"
    checks["security_csv"] = csv_path.exists()
    if not checks["security_csv"]:
        issues.append("Missing security/ir.model.access.csv")

    # 9. tests_exist
    tests_dir = path / "tests"
    has_tests = tests_dir.is_dir() and any(tests_dir.glob("test_*.py"))
    checks["tests_exist"] = has_tests
    if not has_tests:
        issues.append("Missing tests/ directory with test_*.py files")

    # 10. claude_md
    checks["claude_md"] = (path / "CLAUDE.md").exists()
    if not checks["claude_md"]:
        issues.append("Missing CLAUDE.md documentation")

    # 11. views_exist
    views_dir = path / "views"
    has_views = views_dir.is_dir() and any(views_dir.glob("*.xml"))
    checks["views_exist"] = has_views
    if not has_views:
        issues.append("Missing views/ directory with .xml files")

    # 12. model_descriptions
    model_desc_ok = _check_model_descriptions(path)
    checks["model_descriptions"] = model_desc_ok
    if not model_desc_ok:
        issues.append("Some models in models/ are missing _description")

    # Compute score
    score = sum(_CHECK_WEIGHTS[k] for k, v in checks.items() if v)

    return HealthResult(score=score, checks=checks, issues=issues)


def _check_model_descriptions(addon_path: Path) -> bool:
    """Check that all Python files in models/ with ``_name =`` also have ``_description =``.

    Uses regex pattern matching (not code execution) to detect field definitions.

    Args:
        addon_path: Root directory of the addon.

    Returns:
        True if all models pass (or no models/ dir exists), False otherwise.
    """
    models_dir = addon_path / "models"
    if not models_dir.is_dir():
        return True

    name_pattern = re.compile(r"_name\s*=")
    desc_pattern = re.compile(r"_description\s*=")

    for py_file in sorted(models_dir.glob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if name_pattern.search(content) and not desc_pattern.search(content):
            return False

    return True
