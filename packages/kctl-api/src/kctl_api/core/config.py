"""Profile management and configuration resolution for kctl-api.

ServiceConfig and resolve_connection() are API-specific and kept here.
Profile framework functions delegate to kctl-lib.config; low-level I/O
(load_raw_config, save_raw_config) are kept locally so that the module-level
CONFIG_FILE / CONFIG_DIR names can be patched in tests.

Config format:
  profiles:
    production:
      api:                   # <- kctl-api reads this
        url: https://api.kodeme.io
        ai_url: https://ai.kodeme.io
        api_key: <key>
        database_url: postgresql+asyncpg://...
        redis_url: redis://...
      odoo:                  # <- kctl-odoo reads this
        url: https://erp.kodeme.io
        ...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import kctl_lib.config as _common
import yaml
from kctl_lib.config import (
    ConfigFile,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    remove_profile,
    set_default_profile,
)
from kctl_lib.config import (
    is_service_scoped as _is_service_scoped,
)
from pydantic import BaseModel

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "SERVICE_KEY",
    "ConfigFile",
    "ServiceConfig",
    "_is_service_scoped",
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

CONFIG_DIR: Path = _common.CONFIG_DIR
CONFIG_FILE: Path = _common.CONFIG_FILE

# This CLI's service key.
SERVICE_KEY = "api"

# Env-prefix used for KCTL_API_PROFILE / KCTL_API_URL etc.
_ENV_PREFIX = "KCTL_API"


class ServiceConfig(BaseModel):
    """API-specific service config within a profile."""

    url: str = ""
    ai_url: str = ""
    api_key: str = ""
    database_url: str = ""
    redis_url: str = ""
    project_root: str = ""


# ---------------------------------------------------------------------------
# Low-level I/O — kept local so CONFIG_FILE/CONFIG_DIR are patchable in tests.
# ---------------------------------------------------------------------------


def load_raw_config() -> dict[str, Any]:
    """Load raw YAML config from disk."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        print(f"WARN: Cannot read {CONFIG_FILE}: {e}", file=sys.stderr)
        return {}


def save_raw_config(data: dict[str, Any]) -> None:
    """Write raw config dict to YAML file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    """Load and validate the config file."""
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


# ---------------------------------------------------------------------------
# Profile framework — delegates to kctl-lib where possible.
# ---------------------------------------------------------------------------


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get this CLI's service config from a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})
    if not profile_data:
        return ServiceConfig()

    if _is_service_scoped(profile_data):
        svc_data = profile_data.get(SERVICE_KEY, {})
        if not isinstance(svc_data, dict):
            return ServiceConfig()
        raw: dict[str, Any] = dict(svc_data)
    else:
        raw = dict(profile_data)

    # Expand env vars
    for k, v in raw.items():
        if isinstance(v, str):
            raw[k] = _common.expand_env(v)

    valid = list(ServiceConfig.model_fields)
    raw = {k: v for k, v in raw.items() if k in valid}
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write this CLI's service config into a profile (always scoped format)."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}

    profile = data["profiles"][profile_name]

    if not _is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[SERVICE_KEY] = old_data

    svc_data = svc_config.model_dump(exclude_defaults=False)
    svc_data = {k: v for k, v in svc_data.items() if v}
    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_project_root_from_config(profile_name: str | None = None) -> Path | None:
    """Read project_root from the active config profile.

    Returns None if not configured or the directory does not exist.
    """
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.project_root:
        root = Path(_common.expand_env(svc.project_root)).expanduser()
        if root.is_dir():
            return root
    # Also check env var
    if env_root := os.environ.get("KCTL_API_REPO"):
        root = Path(env_root)
        if root.is_dir():
            return root
    return None


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name from all sources."""
    if profile_name:
        return profile_name
    if env := os.environ.get("KCTL_API_PROFILE"):
        return env
    return get_default_profile()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    ai_url_override: str | None = None,
    api_key_override: str | None = None,
    database_url_override: str | None = None,
    redis_url_override: str | None = None,
) -> tuple[str, str, str, str, str]:
    """Resolve API URL, AI URL, API key, database URL, and Redis URL.

    Returns: (url, ai_url, api_key, database_url, redis_url)

    Priority:
    1. CLI flags (overrides)
    2. KCTL_API_URL / KCTL_API_AI_URL / KCTL_API_KEY / KCTL_API_DATABASE_URL / KCTL_API_REDIS_URL
    3. Profile's api service config
    """
    url = ""
    ai_url = ""
    api_key = ""
    database_url = ""
    redis_url = ""

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.ai_url:
        ai_url = svc.ai_url
    if svc.api_key:
        api_key = svc.api_key
    if svc.database_url:
        database_url = svc.database_url
    if svc.redis_url:
        redis_url = svc.redis_url

    # 2. Environment variables
    if env_url := os.environ.get("KCTL_API_URL"):
        url = env_url
    if env_ai_url := os.environ.get("KCTL_API_AI_URL"):
        ai_url = env_ai_url
    if env_key := os.environ.get("KCTL_API_KEY"):
        api_key = env_key
    if env_db := os.environ.get("KCTL_API_DATABASE_URL"):
        database_url = env_db
    if env_redis := os.environ.get("KCTL_API_REDIS_URL"):
        redis_url = env_redis

    # 1. CLI flags
    if url_override:
        url = url_override
    if ai_url_override:
        ai_url = ai_url_override
    if api_key_override:
        api_key = api_key_override
    if database_url_override:
        database_url = database_url_override
    if redis_url_override:
        redis_url = redis_url_override

    return url, ai_url, api_key, database_url, redis_url
