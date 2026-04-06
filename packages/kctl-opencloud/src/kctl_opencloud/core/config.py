"""Profile management and configuration for kctl-opencloud.

Wraps kctl-lib config framework with OpenCloud-specific service logic.
"""

from __future__ import annotations

import os

from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ConfigFile,
    expand_env,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    is_service_scoped,
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

SERVICE_KEY = "opencloud"


class ServiceConfig(BaseModel):
    """OpenCloud service-specific config within a profile."""

    url: str = ""
    token: str = ""
    container_name: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get OpenCloud service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write OpenCloud service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    for key in ["container_name"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name."""
    return _resolve_active_profile_name(profile_name, env_prefix="KCTL_OPENCLOUD")


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    token_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and token from all sources.

    Priority:
    1. CLI flags (url_override, token_override)
    2. KCTL_OPENCLOUD_URL / KCTL_OPENCLOUD_TOKEN env vars
    3. OC_URL / OC_MACHINE_AUTH_API_KEY env vars
    4. Profile's opencloud service config
    """
    url = ""
    token = ""

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.token:
        token = expand_env(svc.token)

    # 3. OpenCloud env vars
    if env_url := os.environ.get("OC_URL"):
        url = env_url
    if env_token := os.environ.get("OC_MACHINE_AUTH_API_KEY"):
        token = env_token

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_OPENCLOUD_URL"):
        url = env_url
    if env_token := os.environ.get("KCTL_OPENCLOUD_TOKEN"):
        token = env_token

    # 1. CLI flags
    if url_override:
        url = url_override
    if token_override:
        token = token_override

    return url, token


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
    "is_service_scoped",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
