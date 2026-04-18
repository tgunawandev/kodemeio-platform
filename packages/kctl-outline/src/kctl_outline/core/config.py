"""Profile management and configuration resolution.

Shared config at ~/.config/kodemeio/config.yaml supports multiple services.
Each kctl-* CLI declares a SERVICE_KEY and reads its own section within a profile.

Config format:
  profiles:
    kodemeio:
      outline:           # <- kctl-outline reads this
        url: https://outline.kodeme.io
        token: <token>
      authentik:          # <- kctl-ak would read this
        url: https://auth.kodeme.io
        token: <token>

# KCTL-COMMON: extractable
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# This CLI's service key. Other kctl-* CLIs would set their own.
SERVICE_KEY = "outline"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    token: str = ""


class ConfigFile(BaseModel):
    default_profile: str = "default"
    profiles: dict[str, dict[str, Any]] = {}


def load_raw_config() -> dict:
    """Load raw YAML config as dict."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def save_raw_config(data: dict) -> None:
    """Save raw dict to config YAML."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    """Load config file."""
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


def _is_service_scoped(profile_data: dict) -> bool:
    """Check if a profile uses service-scoped format (new) vs flat format (old).

    New format: profiles.production.outline.url
    Old format: profiles.production.url
    """
    return any(isinstance(val, dict) for key, val in profile_data.items())


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get this CLI's service config from a profile.

    Supports both formats:
    - New (scoped): profiles.<name>.outline.url
    - Old (flat):   profiles.<name>.url  (backward compat)
    """
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if not profile_data:
        return ServiceConfig()

    if _is_service_scoped(profile_data):
        svc_data = profile_data.get(SERVICE_KEY, {})
        if isinstance(svc_data, dict):
            return ServiceConfig(**svc_data)
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

    if not _is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[SERVICE_KEY] = old_data

    svc_data = svc_config.model_dump(exclude_defaults=False)
    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_profile_names() -> list[str]:
    """Get all profile names."""
    cfg = load_config()
    return list(cfg.profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict]:
    """Get all service configs in a profile (for display)."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if _is_service_scoped(profile_data):
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


def _expand_token(token: str) -> str:
    """Expand ${ENV_VAR} references in token values."""
    if token.startswith("${") and token.endswith("}"):
        env_name = token[2:-1]
        return os.environ.get(env_name, "")
    return token


def resolve_active_profile_name(
    profile_name: str | None = None,
) -> str:
    """Resolve the active profile name from all sources."""
    if profile_name:
        return profile_name
    if env := os.environ.get("KCTL_OUTLINE_PROFILE"):
        return env
    return get_default_profile()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    token_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and token from all sources.

    Priority:
    1. CLI flags (url_override, token_override)
    2. KCTL_OUTLINE_URL / KCTL_OUTLINE_TOKEN env vars
    3. Profile's outline service config
    """
    url = ""
    token = ""

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.token:
        token = _expand_token(svc.token)

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_OUTLINE_URL"):
        url = env_url
    if env_token := os.environ.get("KCTL_OUTLINE_TOKEN"):
        token = env_token

    # 1. CLI flags
    if url_override:
        url = url_override
    if token_override:
        token = token_override

    return url, token
