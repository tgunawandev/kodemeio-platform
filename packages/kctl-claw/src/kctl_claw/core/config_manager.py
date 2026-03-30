"""JSON config file manager with atomic writes and backup-before-modify."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from kctl_claw.core.models import DiffEntry


class ConfigFile(StrEnum):
    OPENCLAW = "config/openclaw.json"
    MCP_REGISTRY = "config/config.json"
    CRON_JOBS = "config/cron/jobs.json"
    AUTH_PROFILES = "config/auth-profiles.json"


class ConfigManager:
    """Manages JSON config files with atomic writes and backup-before-modify."""

    def __init__(self, project_root: Path):
        self._root = project_root

    def _path(self, config_file: ConfigFile) -> Path:
        return self._root / config_file.value

    def read(self, config_file: ConfigFile) -> dict[str, Any]:
        """Read and parse a JSON config file."""
        path = self._path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            return json.load(f)  # type: ignore[no-any-return]

    def write(self, config_file: ConfigFile, data: dict[str, Any]) -> None:
        """Write JSON config file atomically (write to .tmp, then rename)."""
        path = self._path(config_file)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        tmp_path.rename(path)

    def backup_before_modify(self, config_file: ConfigFile) -> Path:
        """Create a timestamped backup of a config file before modifying it."""
        path = self._path(config_file)
        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        bak_path = path.with_name(f"{path.stem}.bak.{ts}{path.suffix}")
        shutil.copy2(path, bak_path)
        return bak_path

    def diff(self, config_file: ConfigFile, other: dict[str, Any]) -> list[DiffEntry]:
        """Structural diff between local config and another dict (e.g. running config)."""
        local = self.read(config_file)
        entries: list[DiffEntry] = []
        self._diff_recursive(local, other, "", entries)
        return entries

    def _diff_recursive(self, local: Any, remote: Any, path: str, entries: list[DiffEntry]) -> None:
        if isinstance(local, dict) and isinstance(remote, dict):
            all_keys = set(local.keys()) | set(remote.keys())
            for key in sorted(all_keys):
                child_path = f"{path}.{key}" if path else key
                lv = local.get(key)
                rv = remote.get(key)
                if lv != rv:
                    if isinstance(lv, (dict, list)) and isinstance(rv, (dict, list)):
                        self._diff_recursive(lv, rv, child_path, entries)
                    else:
                        entries.append(DiffEntry(path=child_path, local_value=str(lv), remote_value=str(rv)))
        elif isinstance(local, list) and isinstance(remote, list):
            for i, (lv, rv) in enumerate(zip(local, remote, strict=False)):
                if lv != rv:
                    self._diff_recursive(lv, rv, f"{path}[{i}]", entries)
            if len(local) != len(remote):
                entries.append(
                    DiffEntry(
                        path=f"{path}.length",
                        local_value=str(len(local)),
                        remote_value=str(len(remote)),
                    )
                )
        else:
            if local != remote:
                entries.append(DiffEntry(path=path, local_value=str(local), remote_value=str(remote)))

    def validate_json(self, config_file: ConfigFile) -> list[str]:
        """Basic structural validation. Returns list of error messages."""
        errors: list[str] = []
        try:
            data = self.read(config_file)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            return errors
        except FileNotFoundError:
            errors.append(f"File not found: {config_file.value}")
            return errors

        if config_file == ConfigFile.OPENCLAW:
            if "agents" not in data:
                errors.append("Missing required key: agents")
        elif config_file == ConfigFile.MCP_REGISTRY:
            if "mcpServers" not in data:
                errors.append("Missing required key: mcpServers")
        elif config_file == ConfigFile.CRON_JOBS:
            if "jobs" not in data:
                errors.append("Missing required key: jobs")
            else:
                for i, job in enumerate(data["jobs"]):
                    if "id" not in job:
                        errors.append(f"jobs[{i}]: missing 'id'")
                    if "schedule" not in job:
                        errors.append(f"jobs[{i}]: missing 'schedule'")

        return errors

    def exists(self, config_file: ConfigFile) -> bool:
        """Check if config file exists."""
        return self._path(config_file).exists()
