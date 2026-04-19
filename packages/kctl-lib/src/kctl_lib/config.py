"""Profile management and configuration framework for kctl-* CLIs.

Shared config at ~/.config/kodemeio/config.yaml supports multiple services.
Each CLI provides its own SERVICE_KEY (e.g., "next", "odoo", "react").
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigFile(BaseModel):
    """Top-level config file model."""

    default_profile: str = "default"
    profiles: dict[str, dict[str, Any]] = {}


def expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references in a string value."""

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return _ENV_VAR_RE.sub(_replace, value)


def is_service_scoped(profile_data: dict[str, Any]) -> bool:
    """Check if profile data uses service-scoped format (nested dicts)."""
    return any(isinstance(val, dict) for val in profile_data.values())


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


def get_service_config(
    profile_name: str,
    service_key: str,
    valid_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve a service config using prefix inheritance.

    Walks the profile's inheritance chain (see `resolve_inheritance_chain`).
    The first chain member that actually exists in the config AND defines
    `service_key` wins. If the leaf profile does not exist at all in the
    config, returns an empty dict (we do NOT silently walk up to a parent
    when the user-requested profile is itself unknown — that would mask
    typos).
    """
    cfg = load_config()
    if profile_name not in cfg.profiles:
        return {}

    for candidate in resolve_inheritance_chain(profile_name):
        profile_data = cfg.profiles.get(candidate)
        if not profile_data:
            continue

        if is_service_scoped(profile_data):
            svc_data = profile_data.get(service_key, {})
            if not isinstance(svc_data, dict):
                continue
            raw = dict(svc_data)
        else:
            # Legacy flat profile — treat as matching its own service key only.
            if candidate != profile_name:
                continue
            raw = dict(profile_data)

        if not raw:
            continue

        for k, v in raw.items():
            if isinstance(v, str):
                raw[k] = expand_env(v)

        if valid_fields is not None:
            raw = {k: v for k, v in raw.items() if k in valid_fields}

        return raw

    return {}


def set_service_config(profile_name: str, service_key: str, svc_data: dict[str, Any]) -> None:
    """Set a service config within a profile."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}

    profile = data["profiles"][profile_name]

    if not is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[service_key] = old_data

    cleaned = {k: v for k, v in svc_data.items() if v}
    profile[service_key] = cleaned
    save_raw_config(data)


def get_profile_names() -> list[str]:
    """Return all profile names."""
    cfg = load_config()
    return list(cfg.profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict[str, Any]]:
    """Return all service configs within a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})
    if is_service_scoped(profile_data):
        return {k: v for k, v in profile_data.items() if isinstance(v, dict)}
    return {}


def get_default_profile() -> str:
    """Return the default profile name."""
    cfg = load_config()
    return cfg.default_profile


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


def resolve_active_profile_name(profile_name: str | None, env_prefix: str) -> str:
    """Resolve active profile: explicit flag > env var. No silent default.

    Raises:
        ValueError: when neither source is set. The message lists available
            profiles and the env-var name the caller should export.
    """
    if profile_name:
        return profile_name
    env_var = f"{env_prefix}_PROFILE"
    if env := os.environ.get(env_var):
        return env

    available = get_profile_names()
    listing = ", ".join(sorted(available)) if available else "(none configured)"
    raise ValueError(f"No profile specified. Pass --profile/-p or export {env_var}.\nAvailable profiles: {listing}")


def resolve_inheritance_chain(profile_name: str) -> list[str]:
    """Return the prefix-inheritance chain for a profile name.

    Given `idtpp-tpp-odoo-erp`, walks back one `-<segment>` at a time to yield
    `[idtpp-tpp-odoo-erp, idtpp-tpp-odoo, idtpp-tpp, idtpp]`. Callers consume
    this by looking up each name in `cfg.profiles` in order and using the first
    match for a given service key.

    The chain does not require every intermediate name to exist in the config
    — non-existent links are simply skipped by the caller.
    """
    if not profile_name:
        raise ValueError("profile_name cannot be empty")
    chain: list[str] = [profile_name]
    current = profile_name
    while "-" in current:
        current = current.rsplit("-", 1)[0]
        chain.append(current)
    return chain
