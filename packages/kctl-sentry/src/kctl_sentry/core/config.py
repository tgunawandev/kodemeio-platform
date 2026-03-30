"""Config management for kctl-sentry."""

from __future__ import annotations

import os

from kctl_common.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    remove_profile,
    set_default_profile,
)
from kctl_common.config import get_service_config as _get_service_config
from kctl_common.config import (
    resolve_active_profile_name as _resolve_active_profile_name,
)
from kctl_common.config import set_service_config as _set_service_config
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
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "sentry"
ENV_PREFIX = "KCTL_SENTRY"


class ServiceConfig(BaseModel):
    """Sentry-specific service config within a profile."""

    url: str = "https://sentry.io"
    auth_token: str = ""
    organization: str = ""
    default_project: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'sentry' service config from a profile."""
    data = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'sentry' service config within a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Remove empty optional fields
    for key in ["default_project"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    auth_token_override: str | None = None,
) -> tuple[str, str, str, str]:
    """Resolve connection params from all sources.

    Returns (url, auth_token, organization, default_project).

    Priority:
    1. CLI flags (auth_token_override)
    2. KCTL_SENTRY_AUTH_TOKEN / KCTL_SENTRY_ORGANIZATION env vars
    3. SENTRY_AUTH_TOKEN / SENTRY_ORG env vars (native Sentry CLI compat)
    4. Profile's sentry service config
    """
    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    url = svc.url
    auth_token = svc.auth_token
    organization = svc.organization
    default_project = svc.default_project

    # 3. Native Sentry env vars (fallback)
    if env_token := os.environ.get("SENTRY_AUTH_TOKEN"):
        auth_token = env_token
    if env_org := os.environ.get("SENTRY_ORG"):
        organization = env_org

    # 2. KCTL env vars
    if env_token := os.environ.get("KCTL_SENTRY_AUTH_TOKEN"):
        auth_token = env_token
    if env_org := os.environ.get("KCTL_SENTRY_ORGANIZATION"):
        organization = env_org
    if env_url := os.environ.get("KCTL_SENTRY_URL"):
        url = env_url

    # 1. CLI flags
    if auth_token_override:
        auth_token = auth_token_override

    return url, auth_token, organization, default_project
