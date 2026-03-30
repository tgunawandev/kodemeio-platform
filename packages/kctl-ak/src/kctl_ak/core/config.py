"""Profile management and configuration for kctl-ak.

Wraps kctl-common config framework with Authentik-specific service logic.
"""

from __future__ import annotations

import os
from pathlib import Path

from kctl_common.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ConfigFile,
    expand_env,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    is_service_scoped,
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_common.config import get_service_config as _get_service_config
from kctl_common.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_common.config import set_service_config as _set_service_config
from pydantic import BaseModel

# This CLI's service key
SERVICE_KEY = "authentik"


class SmtpProfile(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    from_address: str = ""
    from_name: str = "Kodemeio"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    token: str = ""
    container_name: str = ""
    roles_dir: str = ""
    group_structure: str = ""
    smtp: SmtpProfile | None = None


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Authentik service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    # Handle smtp sub-dict
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Authentik service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Clean empty optional fields
    if svc_data.get("smtp") is None:
        svc_data.pop("smtp", None)
    for key in ["container_name", "roles_dir", "group_structure"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name."""
    return _resolve_active_profile_name(profile_name, env_prefix="KCTL_AK")


def is_container_mode() -> bool:
    """Check if running inside the Authentik container."""
    return Path("/.dockerenv").exists() or Path("/opt/authentik/lifecycle/ak").exists()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    token_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and token from all sources.

    Priority:
    1. CLI flags (url_override, token_override)
    2. KCTL_AK_URL / KCTL_AK_TOKEN env vars
    3. AUTHENTIK_API_URL / AUTHENTIK_BOOTSTRAP_TOKEN env vars
    4. Profile's authentik service config
    5. Auto-detect container mode
    """
    url = ""
    token = ""

    # 5. Auto-detect container mode
    if is_container_mode():
        url = "http://localhost:9000"
        token = os.environ.get("AUTHENTIK_BOOTSTRAP_TOKEN", "")

    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.token:
        token = expand_env(svc.token)

    # 3. Authentik env vars
    if env_url := os.environ.get("AUTHENTIK_API_URL"):
        url = env_url
    if env_token := os.environ.get("AUTHENTIK_BOOTSTRAP_TOKEN"):
        token = env_token

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_AK_URL"):
        url = env_url
    if env_token := os.environ.get("KCTL_AK_TOKEN"):
        token = env_token

    # 1. CLI flags
    if url_override:
        url = url_override
    if token_override:
        token = token_override

    return url, token


def resolve_roles_paths(
    config_override: str | None = None,
    profile_name: str | None = None,
) -> list[Path]:
    """Resolve role definition search paths."""
    paths: list[Path] = []

    if config_override:
        paths.append(Path(config_override))
        return paths

    if env_dir := os.environ.get("AK_ROLES_DIR"):
        paths.append(Path(env_dir))

    # Profile-specific roles_dir
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.roles_dir:
        p = Path(svc.roles_dir).expanduser()
        if p.exists():
            paths.append(p)

    # Global roles_paths from config (not in kctl-common ConfigFile, read from raw)
    raw = load_raw_config()
    for rp in raw.get("roles_paths", []):
        p = Path(rp).expanduser()
        if p.exists():
            paths.append(p)

    # Git repo root detection
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        roles_dir = parent / "roles"
        if roles_dir.is_dir() and (parent / ".git").exists():
            paths.append(roles_dir)
            break

    # User config dir
    user_roles = CONFIG_DIR / "roles"
    if user_roles.is_dir():
        paths.append(user_roles)

    # Bundled in package
    pkg_roles = Path(__file__).parent.parent.parent.parent / "roles"
    if pkg_roles.is_dir():
        paths.append(pkg_roles)

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            result.append(p)

    return result


def resolve_group_structure_path(
    profile_name: str | None = None,
) -> Path | None:
    """Find group-structure.yaml."""
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.group_structure:
        p = Path(svc.group_structure).expanduser()
        if p.exists():
            return p

    raw = load_raw_config()
    if gsp := raw.get("group_structure_path", ""):
        p = Path(gsp).expanduser()
        if p.exists():
            return p

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        gs = parent / "config" / "group-structure.yaml"
        if gs.exists():
            return gs

    user_gs = CONFIG_DIR / "group-structure.yaml"
    if user_gs.exists():
        return user_gs

    return None


# Re-export everything that config_cmd.py needs
__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ConfigFile",
    "SERVICE_KEY",
    "ServiceConfig",
    "SmtpProfile",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "is_container_mode",
    "is_service_scoped",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "resolve_group_structure_path",
    "resolve_roles_paths",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
