"""Profile management — delegates to kctl-lib shared config.

Config lives at ~/.config/kodemeio/config.yaml under the 'rmm' service key:
  profiles:
    production:
      rmm:
        url: https://api-rmm.kodeme.io
        api_key: <trmm-service-api-key>
        mesh_url: https://mesh.kodeme.io
"""

from __future__ import annotations

import os

from pydantic import BaseModel

from kctl_lib.config import (
    get_default_profile,
    get_profile_names,
    get_service_config as _get_service_config,
    remove_profile,
    resolve_active_profile_name as _resolve_active_profile_name,
    set_default_profile,
    set_service_config as _set_service_config,
)

SERVICE_KEY = "rmm"
ENV_PREFIX = "KCTL_RMM"


class ServiceConfig(BaseModel):
    """RMM service-specific config within a profile."""

    url: str = ""
    api_key: str = ""
    mesh_url: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Remove empty values
    svc_data = {k: v for k, v in svc_data.items() if v}
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and API key. Priority: CLI flags > env vars > profile config."""
    url = ""
    api_key = ""

    # 3. Config file profile
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = svc.api_key

    # 2. Environment variables
    if env_url := os.environ.get(f"{ENV_PREFIX}_URL"):
        url = env_url
    if env_key := os.environ.get(f"{ENV_PREFIX}_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key


def resolve_mesh_url(profile_name: str | None = None) -> str:
    """Resolve MeshCentral URL from profile config."""
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    return svc.mesh_url or ""
