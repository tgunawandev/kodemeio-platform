"""Config management for kctl-dbgate.

Shared config at ~/.config/kodemeio/config.yaml, scoped under the "dbgate" key.
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

SERVICE_KEY = "dbgate"
ENV_PREFIX = "KCTL_DBGATE"


class ServiceConfig(BaseModel):
    """DBGate-specific service config within a profile."""

    url: str = ""
    login: str = "admin"
    password: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'dbgate' service config from a profile."""
    data = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'dbgate' service config within a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    login_override: str | None = None,
    password_override: str | None = None,
) -> tuple[str, str, str]:
    """Resolve DBGate URL, login, password from all sources.

    Returns (url, login, password).

    Priority:
    1. CLI flags
    2. KCTL_DBGATE_* env vars
    3. DBGATE_* env vars
    4. Profile's dbgate service config
    """
    url = ""
    login = "admin"
    password = ""

    # 4. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.login:
        login = svc.login
    if svc.password:
        password = svc.password

    # 3. DBGATE env vars
    if env_url := os.environ.get("DBGATE_URL"):
        url = env_url
    if env_login := os.environ.get("DBGATE_LOGIN"):
        login = env_login
    if env_password := os.environ.get("DBGATE_PASSWORD"):
        password = env_password

    # 2. KCTL_DBGATE env vars
    if env_url := os.environ.get("KCTL_DBGATE_URL"):
        url = env_url
    if env_login := os.environ.get("KCTL_DBGATE_LOGIN"):
        login = env_login
    if env_password := os.environ.get("KCTL_DBGATE_PASSWORD"):
        password = env_password

    # 1. CLI flags
    if url_override:
        url = url_override
    if login_override:
        login = login_override
    if password_override:
        password = password_override

    return url, login, password
