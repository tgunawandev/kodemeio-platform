"""Config management for kctl-github."""

from __future__ import annotations

from kctl_common.config import (
    get_all_services_in_profile,
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
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_profile_names",
    "get_service_config",
    "remove_profile",
    "resolve_active_profile_name",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "github"
ENV_PREFIX = "KCTL_GITHUB"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    token: str = ""  # GitHub Personal Access Token
    organization: str = "tgunawandev"  # GitHub org or username
    repo_prefix: str = "kodemeio-"  # Filter repos by this prefix


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'github' service config from a profile."""
    data = _get_service_config(profile_name, SERVICE_KEY, list(ServiceConfig.model_fields.keys()))
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'github' service config within a profile."""
    cleaned = {k: v for k, v in svc_config.model_dump().items() if v}
    _set_service_config(profile_name, SERVICE_KEY, cleaned)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)
