"""Profile-based configuration for kctl-op.

Uses kctl-lib's shared config framework at ~/.config/kodemeio/config.yaml
with SERVICE_KEY = "op" for service-scoped profile isolation.
"""

from __future__ import annotations

import os

from kctl_lib.config import (
    CONFIG_FILE as CONFIG_FILE,
)
from kctl_lib.config import (
    expand_env,
    resolve_active_profile_name,
)
from kctl_lib.config import (
    get_all_services_in_profile as get_all_services_in_profile,
)
from kctl_lib.config import (
    get_default_profile as get_default_profile,
)
from kctl_lib.config import (
    get_profile_names as get_profile_names,
)
from kctl_lib.config import (
    get_service_config as _get_service_config_raw,
)
from kctl_lib.config import (
    load_raw_config as load_raw_config,
)
from kctl_lib.config import (
    remove_profile as remove_profile,
)
from kctl_lib.config import (
    save_raw_config as save_raw_config,
)
from kctl_lib.config import (
    set_default_profile as set_default_profile,
)
from kctl_lib.config import (
    set_service_config as _set_service_config_raw,
)
from pydantic import BaseModel

SERVICE_KEY = "op"

# Defaults embedded from config/default.yaml
DEFAULT_EXCLUDE_PATTERNS = [
    "**/.env.example",
    "**/.env.*.example",
    "**/*.env.example",
    "**/.env.tmp",
    "**/node_modules/**",
    "**/archived/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "kodemeio-op/**",
]

DEFAULT_ENV_MAPPINGS = {
    ".env": "dev",
    ".env.development": "dev",
    ".env.staging": "staging",
    ".env.production": "production",
    ".env.prod": "production",
    ".env.local": "local",
}

DEFAULT_CUSTOM_ENV_PATTERN = r"\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)"


class ServiceConfig(BaseModel):
    """1Password service-specific config within a profile."""

    vault: str = ""
    service_account_token: str = ""
    scan_roots: list[str] = []
    exclude_patterns: list[str] = DEFAULT_EXCLUDE_PATTERNS
    env_mappings: dict[str, str] = DEFAULT_ENV_MAPPINGS
    custom_env_pattern: str = DEFAULT_CUSTOM_ENV_PATTERN


_VALID_FIELDS = list(ServiceConfig.model_fields.keys())


def get_service_config(profile_name: str) -> ServiceConfig:
    """Load ServiceConfig for the given profile."""
    raw = _get_service_config_raw(profile_name, SERVICE_KEY, valid_fields=_VALID_FIELDS)
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Save ServiceConfig for the given profile."""
    data = svc_config.model_dump(exclude_defaults=True)
    _set_service_config_raw(profile_name, SERVICE_KEY, data)


def resolve_config(
    profile_name: str | None = None,
    vault_override: str | None = None,
    token_override: str | None = None,
) -> ServiceConfig:
    """Resolve 1Password connection config with priority:

    1. CLI flags (vault_override, token_override)
    2. KCTL_OP_VAULT / KCTL_OP_TOKEN env vars
    3. OP_SERVICE_ACCOUNT_TOKEN env var (token only)
    4. Profile config from ~/.config/kodemeio/config.yaml
    """
    # Determine profile
    pname = resolve_active_profile_name(profile_name, "KCTL_OP")

    # Load profile config as base
    svc = get_service_config(pname)

    # Layer 4: profile config (already loaded)
    vault = svc.vault
    token = expand_env(svc.service_account_token) if svc.service_account_token else ""
    scan_roots = svc.scan_roots

    # Layer 3: OP_SERVICE_ACCOUNT_TOKEN env var
    if not token:
        token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN", "")

    # Layer 2: KCTL_OP_* env vars
    vault = os.environ.get("KCTL_OP_VAULT", vault)
    token = os.environ.get("KCTL_OP_TOKEN", token)

    # Layer 1: CLI flags (highest priority)
    if vault_override:
        vault = vault_override
    if token_override:
        token = token_override

    return ServiceConfig(
        vault=vault,
        service_account_token=token,
        scan_roots=scan_roots,
        exclude_patterns=svc.exclude_patterns,
        env_mappings=svc.env_mappings,
        custom_env_pattern=svc.custom_env_pattern,
    )
