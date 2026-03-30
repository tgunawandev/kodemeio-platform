"""Configuration for kctl-claude."""

from kctl_common.config import get_service_config, load_config
from pydantic import BaseModel

SERVICE_KEY = "claude"


class ServiceConfig(BaseModel):
    """Service-specific configuration for Claude Code."""

    config_dir: str = ""
    backup_dir: str = ""


def load_claude_config(profile: str = "") -> ServiceConfig:
    """Load Claude service config from the shared kodemeio config file."""
    cfg = load_config()
    profile_name = profile or cfg.default_profile
    service_data = get_service_config(profile_name, SERVICE_KEY)
    return ServiceConfig(**service_data)
