"""Profile management and configuration for kctl-waha.

Wraps kctl-common config framework with WAHA-specific service logic.
"""

from __future__ import annotations

import os

from kctl_common.config import (
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
from kctl_common.config import get_service_config as _get_service_config
from kctl_common.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_common.config import set_service_config as _set_service_config
from pydantic import BaseModel

# This CLI's service key
SERVICE_KEY = "waha"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    api_key: str = ""
    bridge_url: str = ""
    container_name: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get WAHA service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write WAHA service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional fields
    for key in ["bridge_url", "container_name"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name."""
    return _resolve_active_profile_name(profile_name, env_prefix="KCTL_WAHA")


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and API key from all sources.

    Priority:
    1. CLI flags (url_override, api_key_override)
    2. KCTL_WAHA_URL / KCTL_WAHA_API_KEY env vars
    3. WAHA_API_URL / WAHA_API_KEY env vars
    4. Profile's waha service config
    """
    url = ""
    api_key = ""

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = expand_env(svc.api_key)

    # 3. WAHA env vars
    if env_url := os.environ.get("WAHA_API_URL"):
        url = env_url
    if env_key := os.environ.get("WAHA_API_KEY"):
        api_key = env_key

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_WAHA_URL"):
        url = env_url
    if env_key := os.environ.get("KCTL_WAHA_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key


def resolve_bridge_url(
    profile_name: str | None = None,
    bridge_override: str | None = None,
) -> str:
    """Resolve bridge sidecar URL.

    Priority:
    1. CLI flag (bridge_override)
    2. KCTL_WAHA_BRIDGE_URL env var
    3. WAHA_BRIDGE_URL env var
    4. Profile's waha.bridge_url config
    5. Default: http://localhost:3050
    """
    bridge_url = "http://localhost:3050"

    # 4. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.bridge_url:
        bridge_url = svc.bridge_url

    # 3. WAHA env var
    if env_url := os.environ.get("WAHA_BRIDGE_URL"):
        bridge_url = env_url

    # 2. KCTL env var
    if env_url := os.environ.get("KCTL_WAHA_BRIDGE_URL"):
        bridge_url = env_url

    # 1. CLI flag
    if bridge_override:
        bridge_url = bridge_override

    return bridge_url


# Re-exports for config_cmd.py compatibility
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
    "resolve_bridge_url",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
