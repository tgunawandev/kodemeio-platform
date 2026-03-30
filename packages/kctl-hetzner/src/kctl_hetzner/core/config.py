"""Profile management and configuration resolution for Hetzner.

Uses kctl-common config framework with Hetzner-specific service config.
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
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_common.config import (
    get_service_config as _get_service_config,
)
from kctl_common.config import (
    resolve_active_profile_name as _resolve_active_profile_name,
)
from kctl_common.config import (
    set_service_config as _set_service_config,
)
from pydantic import BaseModel

SERVICE_KEY = "hetzner"
ENV_PREFIX = "KCTL_HETZNER"


class ServiceConfig(BaseModel):
    """Hetzner service config within a profile."""

    token: str = ""
    dns_token: str = ""
    default_location: str = "fsn1"
    default_image: str = "ubuntu-24.04"
    default_server_type: str = "cx22"


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Hetzner service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields),
    )
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Save Hetzner service config to a profile."""
    svc_data = {k: v for k, v in svc_config.model_dump(exclude_defaults=False).items() if v}
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > KCTL_HETZNER_PROFILE > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    token_override: str | None = None,
    dns_token_override: str | None = None,
) -> tuple[str, str]:
    """Resolve Cloud token and DNS token."""
    token = ""
    dns_token = ""

    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.token:
        token = svc.token  # already env-expanded by kctl-common
    if svc.dns_token:
        dns_token = svc.dns_token

    if env_token := os.environ.get("HCLOUD_TOKEN"):
        token = env_token
    if env_dns := os.environ.get("HETZNER_DNS_TOKEN"):
        dns_token = env_dns

    if env_token := os.environ.get("KCTL_HETZNER_TOKEN"):
        token = env_token
    if env_dns := os.environ.get("KCTL_HETZNER_DNS_TOKEN"):
        dns_token = env_dns

    if token_override:
        token = token_override
    if dns_token_override:
        dns_token = dns_token_override

    return token, dns_token


__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ConfigFile",
    "ENV_PREFIX",
    "SERVICE_KEY",
    "ServiceConfig",
    "expand_env",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
