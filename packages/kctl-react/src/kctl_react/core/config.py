"""Config management — delegates to kctl-lib with react-specific ServiceConfig.

Core I/O (load_raw_config / save_raw_config) uses module-level CONFIG_DIR /
CONFIG_FILE so that tests can monkeypatch those names.  is_service_scoped and
ConfigFile are re-used from kctl_lib; all file-touching functions are local.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml
from kctl_lib.config import ConfigFile, is_service_scoped
from pydantic import BaseModel

SERVICE_KEY = "react"
ENV_PREFIX = "KCTL_REACT"

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_project_root",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    project_root: str = ""
    api_url: str = ""
    odoo_url: str = ""
    odoo_db: str = ""


def load_raw_config() -> dict[str, Any]:
    """Load raw YAML config from disk."""
    import kctl_react.core.config as _self

    cf = _self.CONFIG_FILE
    if not cf.exists():
        return {}
    try:
        with open(cf) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        print(f"WARN: Cannot read {cf}: {e}", file=sys.stderr)
        return {}


def save_raw_config(data: dict[str, Any]) -> None:
    """Write raw config dict to YAML file."""
    import kctl_react.core.config as _self

    cd = _self.CONFIG_DIR
    cf = _self.CONFIG_FILE
    cd.mkdir(parents=True, exist_ok=True)
    with open(cf, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    """Load and validate the config file."""
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'react' service config from a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})
    if not profile_data:
        return ServiceConfig()
    if is_service_scoped(profile_data):
        svc_data = profile_data.get(SERVICE_KEY, {})
        if isinstance(svc_data, dict):
            return ServiceConfig(**{k: v for k, v in svc_data.items() if k in ServiceConfig.model_fields})
        return ServiceConfig()
    else:
        return ServiceConfig(**{k: v for k, v in profile_data.items() if k in ServiceConfig.model_fields})


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'react' service config within a profile."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}
    profile = data["profiles"][profile_name]
    if not is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[SERVICE_KEY] = old_data
    svc_data = svc_config.model_dump(exclude_defaults=False)
    for key in list(svc_data.keys()):
        if not svc_data.get(key):
            svc_data.pop(key, None)
    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_profile_names() -> list[str]:
    """Return all profile names."""
    return list(load_config().profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict[str, Any]]:
    """Return all service configs within a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})
    if is_service_scoped(profile_data):
        return {k: v for k, v in profile_data.items() if isinstance(v, dict)}
    return {}


def get_default_profile() -> str:
    """Return the default profile name."""
    return load_config().default_profile


def set_default_profile(name: str) -> None:
    """Set the default profile name."""
    data = load_raw_config()
    data["default_profile"] = name
    save_raw_config(data)


def remove_profile(name: str) -> None:
    """Remove a profile by name."""
    data = load_raw_config()
    profiles = data.get("profiles", {})
    profiles.pop(name, None)
    if data.get("default_profile") == name:
        data["default_profile"] = next(iter(profiles), "default")
    save_raw_config(data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    if profile_name:
        return profile_name
    if env := os.environ.get(f"{ENV_PREFIX}_PROFILE"):
        return env
    return get_default_profile()


def resolve_project_root(
    profile_name: str | None = None,
    root_override: str | None = None,
) -> Path:
    """Resolve the monorepo project root.

    Priority:
    1. CLI --root flag
    2. KCTL_REACT_ROOT env var
    3. Profile config project_root
    4. Auto-detect from CWD (walk up to find turbo.json)
    """
    # 1. CLI override
    if root_override:
        return Path(root_override)

    # 2. Env var
    if env_root := os.environ.get("KCTL_REACT_ROOT"):
        return Path(env_root)

    # 3. Profile config
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.project_root:
        return Path(svc.project_root)

    # 4. Auto-detect from CWD
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "turbo.json").exists() and (parent / "apps").is_dir():
            return parent

    # Fallback to CWD
    return cwd
