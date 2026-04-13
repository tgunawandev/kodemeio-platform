"""Mattermost profile resolution (minimal — full CRUD lands in Task 5).

Config format:
  default_profile: default
  profiles:
    default:
      mattermost:
        url: https://mm.kodeme.io
        token: ${MM_TOKEN}
        ssh_host: mm-prod-01
        ssh_user: root
        compose_path: /opt/mattermost/docker-compose.yml
        compose_service: mattermost
        timeout: 30
"""

from __future__ import annotations

import os
from typing import Any

from kctl_lib.config import expand_env, load_raw_config
from kctl_lib.exceptions import ConfigError

SERVICE_KEY = "mattermost"
ENV_PROFILE = "KCTL_MM_PROFILE"


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

    name = profile_name or os.environ.get(ENV_PROFILE) or raw.get("default_profile") or "default"

    profile_data = profiles.get(name)
    if not profile_data:
        raise ConfigError(f"Profile '{name}' not found in config.")

    svc = profile_data.get(SERVICE_KEY)
    if not isinstance(svc, dict) or not svc:
        raise ConfigError(
            f"Profile '{name}' has no '{SERVICE_KEY}' service section. Run `kctl-mm config init` to configure it."
        )

    return _expand_values(svc)
