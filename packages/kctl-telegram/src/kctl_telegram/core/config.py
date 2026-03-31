"""Profile management and configuration for kctl-telegram.

Uses kctl-lib config framework with SERVICE_KEY = "telegram".
"""

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
    resolve_active_profile_name,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

SERVICE_KEY = "telegram"
ENV_PREFIX = "KCTL_TELEGRAM"


class ServiceConfig(BaseModel):
    """Telegram-specific service config within a profile."""

    url: str = ""
    api_key: str = ""
    container_name: str = ""


_VALID_FIELDS = list(ServiceConfig.model_fields.keys())


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Telegram service config from a profile."""
    raw = _get_service_config(profile_name, SERVICE_KEY, valid_fields=_VALID_FIELDS)
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Telegram service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional fields
    for key in ["container_name"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and API key from all sources.

    Priority:
    1. CLI flags (url_override, api_key_override)
    2. KCTL_TELEGRAM_URL / KCTL_TELEGRAM_API_KEY env vars
    3. TELEGRAM_API_URL / TELEGRAM_API_KEY env vars
    4. Profile's telegram service config
    """
    url = ""
    api_key = ""

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name, ENV_PREFIX)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = svc.api_key

    # 3. Telegram env vars
    if env_url := os.environ.get("TELEGRAM_API_URL"):
        url = env_url
    if env_key := os.environ.get("TELEGRAM_API_KEY"):
        api_key = env_key

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_TELEGRAM_URL"):
        url = env_url
    if env_key := os.environ.get("KCTL_TELEGRAM_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key


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
