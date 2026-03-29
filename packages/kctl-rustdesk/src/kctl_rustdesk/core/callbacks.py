"""Application context for kctl-rustdesk."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_rustdesk.core.config import resolve_connection
from kctl_rustdesk.core.executor import RustDeskExecutor


@dataclass
class AppContext(AppContextBase):
    """RustDesk CLI context with lazy-loaded executor."""

    host_override: str | None = None
    _executor: RustDeskExecutor | None = field(default=None, repr=False, init=False)

    @property
    def executor(self) -> RustDeskExecutor:
        """Lazy-initialized RustDesk executor."""
        if self._executor is None:
            config = resolve_connection(
                profile_name=self.profile,
                host_override=self.host_override,
            )
            self._executor = RustDeskExecutor(config)
        return self._executor
