"""Profile management and configuration resolution for kctl-cf.

Wraps kctl-lib config functions with Cloudflare-specific defaults.
"""

from __future__ import annotations

import os

from kctl_lib.config import (
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
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

# This CLI's service key
SERVICE_KEY = "cloudflare"

ENV_PREFIX = "KCTL_CLOUDFLARE"


class ServiceConfig(BaseModel):
    """Cloudflare-specific service config within a profile."""

    api_token: str = ""
    account_id: str = ""
    terraform_dir: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Cloudflare service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Cloudflare service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Remove empty optional fields
    for key in ["terraform_dir"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(
    profile_name: str | None = None,
) -> str:
    """Resolve the active profile name from all sources."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    api_token_override: str | None = None,
    account_id_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API token and account ID from all sources.

    Priority:
    1. CLI flags (api_token_override, account_id_override)
    2. KCTL_CLOUDFLARE_API_TOKEN / KCTL_CLOUDFLARE_ACCOUNT_ID env vars
    3. CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID env vars
    4. Profile's cloudflare service config
    """
    api_token = ""
    account_id = ""

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.api_token:
        api_token = svc.api_token
    if svc.account_id:
        account_id = svc.account_id

    # 3. Cloudflare env vars (fallback)
    if env_token := os.environ.get("CLOUDFLARE_API_TOKEN"):
        api_token = env_token
    if env_account := os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        account_id = env_account

    # 2. KCTL env vars
    if env_token := os.environ.get("KCTL_CLOUDFLARE_API_TOKEN"):
        api_token = env_token
    if env_account := os.environ.get("KCTL_CLOUDFLARE_ACCOUNT_ID"):
        account_id = env_account

    # 1. CLI flags
    if api_token_override:
        api_token = api_token_override
    if account_id_override:
        account_id = account_id_override

    return api_token, account_id


def resolve_terraform_dir(profile_name: str | None = None) -> str:
    """Resolve the terraform working directory from profile config."""
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    return svc.terraform_dir


# Re-export everything that commands import
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
    "resolve_terraform_dir",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
