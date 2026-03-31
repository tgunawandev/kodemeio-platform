"""Config management for kctl-linear."""

from __future__ import annotations

from kctl_lib.config import (
    get_all_services_in_profile,
    get_profile_names,
    remove_profile,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import (
    resolve_active_profile_name as _resolve_active_profile_name,
)
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

__all__ = [
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_profile_names",
    "get_service_config",
    "remove_profile",
    "resolve_active_profile_name",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "linear"
ENV_PREFIX = "KCTL_LINEAR"


class ServiceConfig(BaseModel):
    """Linear service-specific config within a profile."""

    api_key: str = ""  # Linear API key (no Bearer prefix needed)
    default_team: str = ""  # Default team key (e.g., "KOD")


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'linear' service config from a profile."""
    data = _get_service_config(profile_name, SERVICE_KEY, list(ServiceConfig.model_fields.keys()))
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'linear' service config within a profile."""
    cleaned = {k: v for k, v in svc_config.model_dump().items() if v}
    _set_service_config(profile_name, SERVICE_KEY, cleaned)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)
