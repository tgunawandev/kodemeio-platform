"""Profile management and configuration for kctl-mailcow.

Wraps kctl-lib config framework with Mailcow-specific service logic.
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

# This CLI's service key
SERVICE_KEY = "mailcow"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    api_key: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Mailcow service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Mailcow service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name."""
    return _resolve_active_profile_name(profile_name, env_prefix="KCTL_MAILCOW")


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and API key from all sources.

    Priority:
    1. CLI flags (url_override, api_key_override)
    2. KCTL_MAILCOW_URL / KCTL_MAILCOW_API_KEY env vars
    3. Profile's mailcow service config
    """
    url = ""
    api_key = ""

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = expand_env(svc.api_key)

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_MAILCOW_URL"):
        url = env_url
    if env_key := os.environ.get("KCTL_MAILCOW_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key


# Re-export everything that config_cmd.py needs
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
