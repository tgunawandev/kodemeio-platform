"""Profile management and config resolution for kctl-accurate.

Stores credentials at ``profiles.<name>.accurate.*`` in
``~/.config/kodemeio/config.yaml`` (the kctl-* shared config).

Resolution order (highest wins):
    1. CLI flags (passed as ``*_override`` kwargs)
    2. ``KCTL_ACCURATE_*`` env vars
    3. Profile config file
    4. ServiceConfig defaults (blank)
"""

from __future__ import annotations

import os
from typing import cast

from kctl_lib.exceptions import ConfigError
from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ConfigFile,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config_raw
from kctl_lib.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_lib.config import set_service_config as _set_service_config_raw
from pydantic import BaseModel

SERVICE_KEY = "accurate"
ENV_PREFIX = "KCTL_ACCURATE"


class ServiceConfig(BaseModel):
    """Accurate Online tenant config within a profile."""

    api_token: str = ""
    signature_secret: str = ""
    db_id: int = 0
    host: str = ""
    db_alias: str = ""
    default_modified_since_days: int = 0


def get_service_config(profile_name: str) -> ServiceConfig:
    """Load the accurate-section of a profile (or blank ServiceConfig if absent)."""
    raw = _get_service_config_raw(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write the accurate-section of a profile."""
    _set_service_config_raw(profile_name, SERVICE_KEY, svc_config.model_dump(exclude_defaults=False))


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    return cast(str, _resolve_active_profile_name(profile_name, ENV_PREFIX))


def mask_secret(secret: str) -> str:
    """Mask a secret for display. ``first4****last4`` for >=10 chars."""
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) < 10:
        return "****"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def resolve_connection(
    profile_name: str | None = None,
    api_token_override: str | None = None,
    signature_secret_override: str | None = None,
    db_id_override: int | None = None,
    host_override: str | None = None,
) -> ServiceConfig:
    """Resolve the effective ServiceConfig from all sources.

    Priority: CLI overrides > KCTL_ACCURATE_* env > profile file > defaults.
    Never raises on missing fields — that decision belongs to the client
    constructor and ``doctor`` checks.
    """
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)

    # Env vars.
    if (env := os.environ.get(f"{ENV_PREFIX}_API_TOKEN")) is not None:
        svc.api_token = env
    if (env := os.environ.get(f"{ENV_PREFIX}_SIGNATURE_SECRET")) is not None:
        svc.signature_secret = env
    if (env := os.environ.get(f"{ENV_PREFIX}_DB_ID")) is not None:
        try:
            svc.db_id = int(env)
        except ValueError as exc:
            raise ConfigError(f"KCTL_ACCURATE_DB_ID must be an integer, got: {env!r}") from exc
    if (env := os.environ.get(f"{ENV_PREFIX}_HOST")) is not None:
        svc.host = env

    # CLI overrides.
    if api_token_override is not None:
        svc.api_token = api_token_override
    if signature_secret_override is not None:
        svc.signature_secret = signature_secret_override
    if db_id_override is not None:
        svc.db_id = db_id_override
    if host_override is not None:
        svc.host = host_override

    return svc


__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ENV_PREFIX",
    "ConfigFile",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "load_config",
    "load_raw_config",
    "mask_secret",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
