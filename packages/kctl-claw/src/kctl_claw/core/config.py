"""Profile management and configuration resolution.

Profile framework delegated to kctl-common. ServiceConfig and
resolve_project_root are claw-specific and kept locally.

Config format:
  profiles:
    default:
      claw:
        project_root: /path/to/kodemeio-openclaw
        gateway_url: https://openclaw.kodeme.io
        gateway_token: ${OPENCLAW_GATEWAY_TOKEN}
        compose_file: docker-compose.prod.yml
        env_file: .env.prod
"""

from __future__ import annotations

import os
from pathlib import Path

from kctl_common.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    get_default_profile,
    get_profile_names,
    load_raw_config,
    remove_profile,
    resolve_active_profile_name,
    save_raw_config,
    set_default_profile,
)
from kctl_common.config import (
    get_service_config as _get_service_config,
)
from kctl_common.config import (
    set_service_config as _set_service_config,
)
from pydantic import BaseModel

from kctl_claw.core.exceptions import ConfigError

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile",
    "resolve_project_root",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "claw"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    project_root: str = ""
    gateway_url: str = ""
    gateway_token: str = ""
    compose_file: str = "docker-compose.prod.yml"
    env_file: str = ".env.prod"


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get claw service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc: ServiceConfig) -> None:
    """Save claw service config to a profile."""
    _set_service_config(profile_name, SERVICE_KEY, svc.model_dump(exclude_defaults=False))


def resolve_active_profile(profile_override: str | None = None) -> str:
    """Resolve the active profile: CLI flag > env > config default."""
    return resolve_active_profile_name(profile_override, "KCTL_CLAW")


def resolve_project_root(
    profile_name: str | None = None,
    root_override: str | None = None,
) -> Path:
    """Resolve project root: CLI flag > env > config > auto-detect."""
    if root_override:
        return Path(root_override)

    env_root = os.environ.get("KCTL_CLAW_ROOT")
    if env_root:
        return Path(env_root)

    if profile_name:
        svc = get_service_config(profile_name)
        if svc.project_root:
            return Path(svc.project_root)

    # Auto-detect: walk up from cwd looking for config/openclaw.json
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "config" / "openclaw.json").exists() and (parent / "docker-compose.prod.yml").exists():
            return parent

    raise ConfigError("Cannot find project root. Use --root, set KCTL_CLAW_ROOT, or run from inside kodemeio-openclaw.")
