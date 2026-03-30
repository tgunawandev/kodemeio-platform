"""Exception hierarchy — re-exported from kctl-common."""

from kctl_common.exceptions import (
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)

__all__ = ["CommandError", "ConfigError", "KctlError", "NotFoundError"]
