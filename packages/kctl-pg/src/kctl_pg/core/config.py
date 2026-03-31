"""Profile management and configuration resolution for kctl-pg.

Delegates generic config operations to kctl-lib. Keeps PostgreSQL-specific
ServiceConfig model and resolve_connection() logic local.

Config format:
  profiles:
    production:
      postgres:              # <- kctl-pg reads this
        host: 10.0.0.3
        port: 5432
        user: postgres
        password: ${PG_PASSWORD}
        ssh_host: 49.13.14.79
        ssh_port: 22
        ssh_user: root
        ssh_key: ~/.ssh/id_ed25519
        databases:
          - authentik
          - odoo
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
SERVICE_KEY = "postgres"

# Env prefix for profile resolution.
_ENV_PREFIX = "KCTL_PG"


class ServiceConfig(BaseModel):
    """PostgreSQL service config within a profile."""

    host: str = ""
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key: str = "~/.ssh/id_ed25519"
    databases: list[str] = []


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get PostgreSQL service config from a profile."""
    raw = _get_service_config_raw(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write PostgreSQL service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional fields
    if not svc_data.get("databases"):
        svc_data.pop("databases", None)
    _set_service_config_raw(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name from all sources."""
    return _resolve_active_profile_name(profile_name, _ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    host_override: str | None = None,
    port_override: int | None = None,
    user_override: str | None = None,
    password_override: str | None = None,
) -> ServiceConfig:
    """Resolve PostgreSQL connection config from all sources.

    Priority:
    1. CLI flags (overrides)
    2. KCTL_PG_* env vars
    3. Standard PG* env vars
    4. Config file profile
    """
    # 4. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)

    # 3. Standard PG env vars
    if env_host := os.environ.get("PGHOST"):
        svc.host = env_host
    if env_port := os.environ.get("PGPORT"):
        svc.port = int(env_port)
    if env_user := os.environ.get("PGUSER"):
        svc.user = env_user
    if env_pass := os.environ.get("PGPASSWORD"):
        svc.password = env_pass

    # 2. KCTL_PG env vars
    if env_host := os.environ.get("KCTL_PG_HOST"):
        svc.host = env_host
    if env_port := os.environ.get("KCTL_PG_PORT"):
        svc.port = int(env_port)
    if env_user := os.environ.get("KCTL_PG_USER"):
        svc.user = env_user
    if env_pass := os.environ.get("KCTL_PG_PASSWORD"):
        svc.password = env_pass
    if env_ssh := os.environ.get("KCTL_PG_SSH_HOST"):
        svc.ssh_host = env_ssh

    # 1. CLI flags
    if host_override:
        svc.host = host_override
    if port_override:
        svc.port = port_override
    if user_override:
        svc.user = user_override
    if password_override:
        svc.password = password_override

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
