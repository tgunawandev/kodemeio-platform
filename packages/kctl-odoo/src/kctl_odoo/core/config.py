"""Profile management and configuration resolution.

Shared config at ~/.config/kodemeio/config.yaml supports multiple services.
Each kctl-* CLI declares a SERVICE_KEY and reads its own section within a profile.

Config format:
  profiles:
    production:
      odoo:                # <- kctl-odoo reads this
        url: https://erp.kodeme.io
        database: kodemeio
        username: admin
        api_key: <key>
      authentik:           # <- kctl-ak reads this
        url: https://auth.kodeme.io
        token: <token>
    abcfood:
      odoo:
        url: https://odoo-erp.abcfood.app
        database: abcfood
        username: admin
        api_key: <key>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml
from kctl_lib.config import ConfigFile, is_service_scoped
from kctl_lib.exceptions import ConfigError
from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# This CLI's service key. Other kctl-* CLIs have their own.
SERVICE_KEY = "odoo"
ENV_PREFIX = "KCTL_ODOO"

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_project_root_from_config",
    "get_service_config",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    database: str = ""
    username: str = "admin"
    api_key: str = ""
    project_root: str = ""


def load_raw_config() -> dict[str, Any]:
    """Load raw YAML config from disk."""
    import kctl_odoo.core.config as _self

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
    import kctl_odoo.core.config as _self

    cd = _self.CONFIG_DIR
    cf = _self.CONFIG_FILE
    cd.mkdir(parents=True, exist_ok=True)
    with open(cf, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    """Load config file."""
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get this CLI's service config from a profile.

    Supports both formats:
    - New (scoped): profiles.<name>.odoo.url
    - Old (flat):   profiles.<name>.url  (backward compat)
    """
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
    """Write this CLI's service config into a profile (always scoped format)."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}

    profile = data["profiles"][profile_name]

    # If old flat format, migrate to scoped
    if not is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[SERVICE_KEY] = old_data

    # Write service config
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional fields
    for key in list(svc_data.keys()):
        if not svc_data.get(key) and key != "username":
            svc_data.pop(key, None)

    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_profile_names() -> list[str]:
    """Get all profile names."""
    cfg = load_config()
    return list(cfg.profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict[str, Any]]:
    """Get all service configs in a profile (for display)."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if is_service_scoped(profile_data):
        return {k: v for k, v in profile_data.items() if isinstance(v, dict)}
    else:
        return {SERVICE_KEY: profile_data}


def get_default_profile() -> str:
    """Get the default profile name."""
    cfg = load_config()
    return cfg.default_profile


def set_default_profile(name: str) -> None:
    """Set the default profile."""
    data = load_raw_config()
    data["default_profile"] = name
    save_raw_config(data)


def remove_profile(name: str) -> None:
    """Remove a profile entirely."""
    data = load_raw_config()
    profiles = data.get("profiles", {})
    profiles.pop(name, None)
    if data.get("default_profile") == name:
        data["default_profile"] = next(iter(profiles), "default")
    save_raw_config(data)


def get_project_root_from_config(profile_name: str | None = None) -> Path | None:
    """Read project_root from the active config profile.

    Returns None if not configured or the directory does not exist.
    """
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.project_root:
        root = Path(_expand_env(svc.project_root)).expanduser()
        if root.is_dir():
            return root
    # Also check env var
    if env_root := os.environ.get("KCTL_ODOO_REPO"):
        root = Path(env_root)
        if root.is_dir():
            return root
    return None


def _expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references in config values."""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def resolve_active_profile_name(
    profile_name: str | None = None,
) -> str:
    """Resolve the active profile name from all sources."""
    if profile_name:
        return profile_name
    if env := os.environ.get("KCTL_ODOO_PROFILE"):
        return env
    return get_default_profile()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
    database_override: str | None = None,
    username_override: str | None = None,
) -> tuple[str, str, str, str]:
    """Resolve Odoo URL, database, username, and API key from all sources.

    Returns: (url, database, username, api_key)

    Priority:
    1. CLI flags (overrides)
    2. KCTL_ODOO_URL / KCTL_ODOO_API_KEY / KCTL_ODOO_DATABASE env vars
    3. Profile's odoo service config
    """
    url = ""
    database = ""
    username = "admin"
    api_key = ""

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.database:
        database = svc.database
    if svc.username:
        username = svc.username
    if svc.api_key:
        api_key = _expand_env(svc.api_key)

    # 2. Environment variables
    if env_url := os.environ.get("KCTL_ODOO_URL"):
        url = env_url
    if env_db := os.environ.get("KCTL_ODOO_DATABASE"):
        database = env_db
    if env_user := os.environ.get("KCTL_ODOO_USERNAME"):
        username = env_user
    if env_key := os.environ.get("KCTL_ODOO_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if database_override:
        database = database_override
    if username_override:
        username = username_override
    if api_key_override:
        api_key = api_key_override

    # If nothing resolved the URL, check whether the profile itself is unknown
    # and surface a clearer error than the downstream "No Odoo URL configured".
    if not url:
        all_profiles = get_profile_names()
        if pname not in all_profiles:
            listing = ", ".join(sorted(all_profiles)) if all_profiles else "(none configured)"
            raise ConfigError(
                f"Profile '{pname}' not found in {CONFIG_FILE}.\n"
                f"Available profiles: {listing}\n"
                f"Run 'kctl-odoo config profiles' to list, "
                f"or 'kctl-odoo config add <name> ...' to create one."
            )

    return url, database, username, api_key
