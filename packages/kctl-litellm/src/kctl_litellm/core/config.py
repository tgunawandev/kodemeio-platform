"""Profile management and configuration resolution for kctl-litellm.

Delegates generic config operations to kctl-lib. Keeps LiteLLM-specific
ServiceConfig model and resolve_connection() logic local.

Config format:
  profiles:
    production:
      litellm:              # <- kctl-litellm reads this
        url: https://litellm.kodeme.io
        master_key: ${KCTL_LITELLM_MASTER_KEY}
        salt_key: ${KCTL_LITELLM_SALT_KEY}
        db_url: ${KCTL_LITELLM_DB_URL}
        ssh_host: 49.13.14.79
        ssh_port: 22
        ssh_user: root
        ssh_key: ~/.ssh/id_ed25519
        container_name: litellm
"""

from __future__ import annotations

import os

# Re-export generic config utilities from kctl-lib
from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ConfigFile,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config_raw
from kctl_lib.config import set_service_config as _set_service_config_raw
from pydantic import BaseModel

# This CLI's service key.
SERVICE_KEY = "litellm"

# Env prefix for profile resolution.
_ENV_PREFIX = "KCTL_LITELLM"


class ServiceConfig(BaseModel):
    """LiteLLM service config within a profile."""

    url: str = ""
    master_key: str = ""
    salt_key: str = ""
    db_url: str = ""
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key: str = "~/.ssh/id_ed25519"
    container_name: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get LiteLLM service config from a profile."""
    raw = _get_service_config_raw(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write LiteLLM service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional string fields (keep ssh_port/ssh_user/ssh_key)
    for field in ("url", "master_key", "salt_key", "db_url", "ssh_host", "container_name"):
        if not svc_data.get(field):
            svc_data.pop(field, None)
    _set_service_config_raw(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name from all sources.

    Priority: explicit flag > KCTL_LITELLM_PROFILE env > default_profile in config.
    """
    if profile_name:
        return profile_name
    if env := os.environ.get(f"{_ENV_PREFIX}_PROFILE"):
        return env
    return get_default_profile()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
) -> ServiceConfig:
    """Resolve LiteLLM connection config from all sources.

    Priority:
    1. CLI flags (overrides)
    2. KCTL_LITELLM_* env vars
    3. Config file profile
    """
    # 3. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)

    # 2. KCTL_LITELLM env vars
    if env_url := os.environ.get("KCTL_LITELLM_URL"):
        svc.url = env_url
    if env_mk := os.environ.get("KCTL_LITELLM_MASTER_KEY"):
        svc.master_key = env_mk
    if env_sk := os.environ.get("KCTL_LITELLM_SALT_KEY"):
        svc.salt_key = env_sk
    if env_db := os.environ.get("KCTL_LITELLM_DB_URL"):
        svc.db_url = env_db
    if env_ssh := os.environ.get("KCTL_LITELLM_SSH_HOST"):
        svc.ssh_host = env_ssh
    if env_ssh_port := os.environ.get("KCTL_LITELLM_SSH_PORT"):
        svc.ssh_port = int(env_ssh_port)
    if env_ssh_user := os.environ.get("KCTL_LITELLM_SSH_USER"):
        svc.ssh_user = env_ssh_user
    if env_container := os.environ.get("KCTL_LITELLM_CONTAINER_NAME"):
        svc.container_name = env_container

    # 1. CLI flags
    if url_override:
        svc.url = url_override

    return svc


__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ConfigFile",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
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
