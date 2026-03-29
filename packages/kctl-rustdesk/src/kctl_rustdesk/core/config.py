"""RustDesk service configuration and profile resolution."""

from __future__ import annotations

import os

from pydantic import BaseModel

from kctl_common.config import (
    get_service_config as _get_service_config,
    resolve_active_profile_name as _resolve_active_profile_name,
    set_service_config as _set_service_config,
)

SERVICE_KEY = "rustdesk"
ENV_PREFIX = "KCTL_RUSTDESK"


class ServiceConfig(BaseModel):
    """RustDesk service config within a profile."""

    host: str = "localhost"
    ssh_user: str = "root"
    compose_file: str = "/opt/kodemeio-rustdesk/docker-compose.prod.yml"
    env_file: str = "/opt/kodemeio-rustdesk/.env.prod"
    project_name: str = "kodemeio-rustdesk"
    domain: str = "rustdesk.kodeme.io"


def get_rustdesk_config(profile_name: str) -> ServiceConfig:
    """Load RustDesk config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields),
    )
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_rustdesk_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Save RustDesk config to a profile."""
    svc_data = {k: v for k, v in svc_config.model_dump().items() if v}
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    host_override: str | None = None,
) -> ServiceConfig:
    """Resolve full connection config with overrides."""
    pname = resolve_active_profile(profile_name)
    svc = get_rustdesk_config(pname)

    # Environment variable overrides
    if env_host := os.environ.get(f"{ENV_PREFIX}_HOST"):
        svc = svc.model_copy(update={"host": env_host})
    if env_user := os.environ.get(f"{ENV_PREFIX}_SSH_USER"):
        svc = svc.model_copy(update={"ssh_user": env_user})

    # Explicit override (highest priority)
    if host_override:
        svc = svc.model_copy(update={"host": host_override})

    return svc
