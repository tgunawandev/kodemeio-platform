"""Profile management and configuration resolution for kctl-supa.

Delegates generic config operations to kctl-lib. Keeps Supabase-specific
ServiceConfig model and resolve_connection() logic local.

Config format:
  profiles:
    production:
      supabase:              # <- kctl-supa reads this
        url: https://supa.terakidz.com
        service_role_key: ${KCTL_SUPA_SERVICE_ROLE_KEY}
        anon_key: ${KCTL_SUPA_ANON_KEY}
        db_password: ${KCTL_SUPA_DB_PASSWORD}
        ssh_host: 49.13.14.79
        ssh_port: 22
        ssh_user: root
        ssh_key: ~/.ssh/id_ed25519
        container_prefix: terakidz-supabase
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
from kctl_lib.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_lib.config import set_service_config as _set_service_config_raw
from pydantic import BaseModel

# This CLI's service key.
SERVICE_KEY = "supabase"

# Env prefix for profile resolution.
_ENV_PREFIX = "KCTL_SUPA"


class ServiceConfig(BaseModel):
    """Supabase service config within a profile."""

    url: str = ""
    service_role_key: str = ""
    anon_key: str = ""
    db_password: str = ""
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key: str = "~/.ssh/id_ed25519"
    container_prefix: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Supabase service config from a profile."""
    raw = _get_service_config_raw(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Supabase service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional string fields (keep ssh_port/ssh_user/ssh_key)
    for field in ("url", "service_role_key", "anon_key", "db_password", "ssh_host", "container_prefix"):
        if not svc_data.get(field):
            svc_data.pop(field, None)
    _set_service_config_raw(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name from all sources."""
    return _resolve_active_profile_name(profile_name, _ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
) -> ServiceConfig:
    """Resolve Supabase connection config from all sources.

    Priority:
    1. CLI flags (overrides)
    2. KCTL_SUPA_* env vars
    3. Config file profile
    """
    # 3. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)

    # 2. KCTL_SUPA env vars
    if env_url := os.environ.get("KCTL_SUPA_URL"):
        svc.url = env_url
    if env_srk := os.environ.get("KCTL_SUPA_SERVICE_ROLE_KEY"):
        svc.service_role_key = env_srk
    if env_anon := os.environ.get("KCTL_SUPA_ANON_KEY"):
        svc.anon_key = env_anon
    if env_dbpw := os.environ.get("KCTL_SUPA_DB_PASSWORD"):
        svc.db_password = env_dbpw
    if env_ssh := os.environ.get("KCTL_SUPA_SSH_HOST"):
        svc.ssh_host = env_ssh
    if env_ssh_port := os.environ.get("KCTL_SUPA_SSH_PORT"):
        svc.ssh_port = int(env_ssh_port)
    if env_ssh_user := os.environ.get("KCTL_SUPA_SSH_USER"):
        svc.ssh_user = env_ssh_user
    if env_prefix := os.environ.get("KCTL_SUPA_CONTAINER_PREFIX"):
        svc.container_prefix = env_prefix

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
