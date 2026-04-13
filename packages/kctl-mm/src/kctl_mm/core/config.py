"""Mattermost profile resolution and helpers.

Config format:
  default_profile: default
  profiles:
    default:
      mattermost:
        url: https://mm.idtpp.com
        token: ${MM_TOKEN}
        team: ""
        ssh_host: kod-prod-02
        ssh_user: root
        compose_path: /etc/dokploy/compose/kod-mattermost/code/docker-compose.prod.yml
        compose_service: mattermost
        timeout: 30
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from kctl_lib.config import expand_env, load_raw_config
from kctl_lib.exceptions import ConfigError

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

SERVICE_KEY = "mattermost"
ENV_PROFILE = "KCTL_MM_PROFILE"


class ServiceConfig(BaseModel):
    """Mattermost service config within a profile."""

    url: str = "https://mm.idtpp.com"
    token: str = ""
    team: str = ""
    ssh_host: str = "kod-prod-02"
    ssh_user: str = "root"
    compose_path: str = "/etc/dokploy/compose/kod-mattermost/code/docker-compose.prod.yml"
    compose_service: str = "mattermost"
    timeout: str = "30"


class ConfigFile(BaseModel):
    default_profile: str = "default"
    profiles: dict[str, dict[str, Any]] = {}


def save_raw_config(data: dict) -> None:
    """Save raw dict to config YAML."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


def _is_service_scoped(profile_data: dict) -> bool:
    for _key, val in profile_data.items():
        if isinstance(val, dict):
            return True
    return False


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Mattermost service config from a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if not profile_data:
        return ServiceConfig(url="", token="")

    if _is_service_scoped(profile_data):
        svc_data = profile_data.get(SERVICE_KEY, {})
        if isinstance(svc_data, dict) and svc_data:
            return ServiceConfig(**{**ServiceConfig().model_dump(), **svc_data})
        return ServiceConfig(url="", token="")
    return ServiceConfig(
        url="",
        token="",
        **{k: v for k, v in profile_data.items() if k in ServiceConfig.model_fields},
    )


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Mattermost service config into a profile (service-scoped)."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}

    profile = data["profiles"][profile_name]
    if not _is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        if old_data:
            profile[SERVICE_KEY] = old_data

    svc_data = svc_config.model_dump(exclude_defaults=False)
    for key in list(svc_data.keys()):
        if svc_data.get(key) in ("", None):
            svc_data.pop(key, None)

    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_profile_names() -> list[str]:
    cfg = load_config()
    return list(cfg.profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict]:
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})
    if _is_service_scoped(profile_data):
        return {k: v for k, v in profile_data.items() if isinstance(v, dict)}
    return {SERVICE_KEY: profile_data} if profile_data else {}


def get_default_profile() -> str:
    cfg = load_config()
    return cfg.default_profile


def set_default_profile(name: str) -> None:
    data = load_raw_config()
    data["default_profile"] = name
    save_raw_config(data)


def remove_profile(name: str) -> None:
    data = load_raw_config()
    profiles = data.get("profiles", {})
    profiles.pop(name, None)
    if data.get("default_profile") == name:
        data["default_profile"] = next(iter(profiles), "default")
    save_raw_config(data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    if profile_name:
        return profile_name
    if env := os.environ.get(ENV_PROFILE):
        return env
    return get_default_profile()


def _expand_values(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            out[key] = expand_env(value)
        else:
            out[key] = value
    return out


def resolve_connection(profile_name: str | None = None) -> dict[str, Any]:
    """Resolve the mattermost service config for the active profile.

    Raises ConfigError if the config file, profile, or service section is missing.
    """
    raw = load_raw_config()
    if not raw:
        raise ConfigError(
            "No kctl config found at ~/.config/kodemeio/config.yaml. Run `kctl-mm config init` to create one."
        )

    profiles = raw.get("profiles", {})
    if not profiles:
        raise ConfigError("No profiles defined in config.")

    name = resolve_active_profile_name(profile_name)

    profile_data = profiles.get(name)
    if not profile_data:
        raise ConfigError(f"Profile '{name}' not found in config.")

    svc = profile_data.get(SERVICE_KEY)
    if not isinstance(svc, dict) or not svc:
        raise ConfigError(
            f"Profile '{name}' has no '{SERVICE_KEY}' service section. Run `kctl-mm config init` to configure it."
        )

    return _expand_values(svc)
