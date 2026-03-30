"""Configuration management for kctl-op (1Password library config)."""

import os
from pathlib import Path
from typing import Any

import yaml


def _find_config_path() -> Path:
    """Find the config file path."""
    # Check environment variable first
    if env_path := os.environ.get("OP_SYNC_CONFIG"):
        return Path(env_path)

    # Check current working directory
    cwd_config = Path.cwd() / "config" / "default.yaml"
    if cwd_config.exists():
        return cwd_config

    # Check relative to this file (for development)
    dev_config = Path(__file__).parent.parent.parent.parent / "config" / "default.yaml"
    if dev_config.exists():
        return dev_config

    # Check user home directory
    home_config = Path.home() / ".config" / "kodemeio-op" / "config.yaml"
    if home_config.exists():
        return home_config

    # Return default (may not exist)
    return cwd_config


DEFAULT_CONFIG_PATH = _find_config_path()


class Config:
    """Configuration holder."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

    @property
    def vault(self) -> str:
        """Get 1Password vault name."""
        return self._data.get("op", {}).get("vault", "kodemeio-secrets")

    @property
    def scan_roots(self) -> list[Path]:
        """Get root directories to scan for .env files."""
        roots = self._data.get("scan_roots")
        if roots:
            return [Path(r).expanduser() for r in roots]
        # Backward compatibility: fall back to single scan_root
        root = self._data.get("scan_root")
        if root:
            return [Path(root).expanduser()]
        return []

    @property
    def scan_root(self) -> Path:
        """Get first root directory (backward compatibility)."""
        roots = self.scan_roots
        if roots:
            return roots[0]
        return Path.cwd()

    @property
    def exclude_patterns(self) -> list[str]:
        """Get patterns to exclude from scanning."""
        return self._data.get(
            "exclude_patterns",
            [
                "**/.env.example",
                "**/.env.*.example",
                "**/*.env.example",
                "**/.env.tmp",
                "**/node_modules/**",
                "**/archived/**",
            ],
        )

    @property
    def env_mappings(self) -> dict[str, str]:
        """Get environment file to name mappings."""
        return self._data.get(
            "env_mappings",
            {
                ".env": "dev",
                ".env.development": "dev",
                ".env.staging": "staging",
                ".env.production": "production",
                ".env.prod": "production",
                ".env.local": "local",
            },
        )

    @property
    def custom_env_pattern(self) -> str:
        """Get regex pattern for custom environment files."""
        return self._data.get("custom_env_pattern", r"\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)")

    @property
    def backup_enabled(self) -> bool:
        """Check if backup is enabled."""
        return self._data.get("backup", {}).get("enabled", True)

    @property
    def backup_directory(self) -> Path:
        """Get backup directory."""
        backup_dir = self._data.get("backup", {}).get("directory", "~/.kodemeio-op/backups")
        return Path(backup_dir).expanduser()

    @property
    def max_backups(self) -> int:
        """Get maximum number of backups to keep."""
        return self._data.get("backup", {}).get("max_backups", 10)


# Global config instance
_config: Config | None = None


def get_config(config_path: Path | None = None) -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None or config_path is not None:
        _config = Config(config_path)
    return _config
