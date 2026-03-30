"""Discover .env files in the kodemeio project directories."""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

from kctl_op.core.op_config import get_config


@dataclass
class EnvFile:
    """Represents a discovered .env file."""
    path: Path
    project: str
    environment: str
    scan_root: Path = field(default_factory=lambda: Path("."))

    @property
    def item_title(self) -> str:
        """Get 1Password item title."""
        return f"{self.project}/{self.environment}"

    @property
    def tags(self) -> list[str]:
        """Get 1Password tags."""
        return [f"project:{self.project}", f"env:{self.environment}"]


def get_project_name(file_path: Path, scan_root: Path) -> str:
    """Extract project name from file path.

    The first directory component relative to scan_root is the project name.
    """
    try:
        relative = file_path.relative_to(scan_root)
        # First directory component is the project name
        return relative.parts[0]
    except ValueError:
        # File is not under scan_root
        return file_path.parent.name


def get_environment_name(filename: str, config=None) -> str:
    """Determine environment name from .env filename."""
    if config is None:
        config = get_config()

    # Check direct mappings first
    if filename in config.env_mappings:
        return config.env_mappings[filename]

    # Try custom pattern (e.g., .env.hz.staging -> hz-staging)
    match = re.match(config.custom_env_pattern, filename)
    if match:
        prefix = match.group("prefix")
        env = match.group("env")
        return f"{prefix}-{env}"

    # Handle .env.{suffix} pattern
    if filename.startswith(".env."):
        suffix = filename[5:]  # Remove ".env."
        # Handle compound suffixes like .env.prod.replica
        if "." in suffix:
            parts = suffix.split(".")
            return "-".join(parts)
        return suffix

    # Default to dev
    return "dev"


def is_excluded(file_path: Path, scan_root: Path, exclude_patterns: list[str]) -> bool:
    """Check if file matches any exclusion pattern."""
    try:
        relative = str(file_path.relative_to(scan_root))
    except ValueError:
        relative = str(file_path)

    for pattern in exclude_patterns:
        # Direct match on relative path
        if fnmatch.fnmatch(relative, pattern):
            return True

        # Match on filename
        if fnmatch.fnmatch(file_path.name, pattern.lstrip("*/")):
            return True

        # Check if path starts with a directory pattern (e.g., "kodemeio-op/**")
        if pattern.endswith("/**"):
            dir_pattern = pattern[:-3]  # Remove "/**"
            if relative.startswith(dir_pattern + "/") or relative == dir_pattern:
                return True

        # Check if any parent directory matches specific patterns
        for part in file_path.parts:
            stripped = pattern.strip("*/")
            if part == stripped:
                return True

    return False


def _scan_root_for_env_files(scan_root: Path, config) -> list[EnvFile]:
    """Scan a single root directory for .env files."""
    if not scan_root.exists():
        return []

    env_files: list[EnvFile] = []
    exclude_patterns = config.exclude_patterns

    for file_path in scan_root.rglob(".env*"):
        if not file_path.is_file():
            continue

        if is_excluded(file_path, scan_root, exclude_patterns):
            continue

        filename = file_path.name
        if "example" in filename.lower():
            continue

        if filename.endswith(".tmp"):
            continue

        project = get_project_name(file_path, scan_root)
        environment = get_environment_name(filename, config)

        env_files.append(EnvFile(
            path=file_path,
            project=project,
            environment=environment,
            scan_root=scan_root,
        ))

    return env_files


def discover_env_files(scan_root: Path | None = None) -> list[EnvFile]:
    """Discover all .env files across all configured scan root directories."""
    config = get_config()

    if scan_root is not None:
        # Single root specified explicitly
        scan_roots = [scan_root]
    else:
        scan_roots = config.scan_roots

    env_files: list[EnvFile] = []

    for root in scan_roots:
        env_files.extend(_scan_root_for_env_files(root, config))

    # Sort by project and environment
    env_files.sort(key=lambda f: (f.project, f.environment))

    return env_files


def find_env_file(project: str, environment: str, scan_root: Path | None = None) -> EnvFile | None:
    """Find a specific .env file by project and environment."""
    env_files = discover_env_files(scan_root)

    for env_file in env_files:
        if env_file.project == project and env_file.environment == environment:
            return env_file

    return None
