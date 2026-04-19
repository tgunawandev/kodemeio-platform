"""Profile + service config for kctl-gsc.

Config shape:
  profiles:
    kodemeio-kod-infra-gsc:
      gsc:
        credentials_file: ~/.config/kodemeio/gsc-sa.json
        default_property: sc-domain:kodeme.io
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

SERVICE_KEY = "gsc"


class ServiceConfig(BaseModel):
    credentials_file: str = ""
    default_property: str = ""


def load_raw_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def save_raw_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def get_service_config(profile_name: str) -> ServiceConfig:
    data = load_raw_config()
    pdata = data.get("profiles", {}).get(profile_name, {})
    svc = pdata.get(SERVICE_KEY, {}) if isinstance(pdata, dict) else {}
    if isinstance(svc, dict):
        return ServiceConfig(**svc)
    return ServiceConfig()


def set_service_config(profile_name: str, svc: ServiceConfig) -> None:
    data = load_raw_config()
    data.setdefault("profiles", {}).setdefault(profile_name, {})[SERVICE_KEY] = svc.model_dump(exclude_defaults=False)
    save_raw_config(data)


def get_profile_names() -> list[str]:
    return list(load_raw_config().get("profiles", {}).keys())


def remove_profile(name: str) -> None:
    data = load_raw_config()
    data.get("profiles", {}).pop(name, None)
    save_raw_config(data)


def _expand(value: str) -> str:
    if value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], "")
    return os.path.expanduser(value)


def resolve_active_profile_name(profile_name: str | None) -> str:
    if profile_name:
        return profile_name
    if env := os.environ.get("KCTL_GSC_PROFILE"):
        return env
    names = get_profile_names()
    raise ValueError(
        f"No profile specified. Pass -p/--profile or set KCTL_GSC_PROFILE. Available: {', '.join(names) or '(none)'}"
    )


def resolve_connection(
    profile_name: str | None = None,
    property_override: str | None = None,
    credentials_file_override: str | None = None,
) -> tuple[str, str]:
    """Returns (credentials_file_path, property)."""
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    creds = _expand(svc.credentials_file) if svc.credentials_file else ""
    prop = svc.default_property

    if env_creds := os.environ.get("KCTL_GSC_CREDENTIALS_FILE"):
        creds = _expand(env_creds)
    if env_prop := os.environ.get("KCTL_GSC_PROPERTY"):
        prop = env_prop

    if credentials_file_override:
        creds = _expand(credentials_file_override)
    if property_override:
        prop = property_override

    return creds, prop
