"""Config management for kctl-glitchtip."""

from __future__ import annotations

import os

from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import (
    resolve_active_profile_name as _resolve_active_profile_name,
)
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ENV_PREFIX",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "glitchtip"
ENV_PREFIX = "KCTL_GLITCHTIP"


class ServiceConfig(BaseModel):
    """GlitchTip-specific service config within a profile."""

    url: str = ""
    token: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'glitchtip' service config from a profile."""
    data = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'glitchtip' service config within a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    token_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and token from all sources.

    Returns (url, token).

    Priority:
    1. CLI flags (url_override, token_override)
    2. KCTL_GLITCHTIP_URL / KCTL_GLITCHTIP_TOKEN env vars
    3. GLITCHTIP_API_URL / GLITCHTIP_API_TOKEN env vars
    4. Profile's glitchtip service config
    """
    url = ""
    token = ""

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.token:
        token = svc.token

    # 3. GlitchTip env vars
    if env_url := os.environ.get("GLITCHTIP_API_URL"):
        url = env_url
    if env_token := os.environ.get("GLITCHTIP_API_TOKEN"):
        token = env_token

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_GLITCHTIP_URL"):
        url = env_url
    if env_token := os.environ.get("KCTL_GLITCHTIP_TOKEN"):
        token = env_token

    # 1. CLI flags
    if url_override:
        url = url_override
    if token_override:
        token = token_override

    return url, token
