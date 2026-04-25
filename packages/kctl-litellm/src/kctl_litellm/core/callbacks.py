"""Typer global callback and shared context for kctl-litellm."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_litellm.core.config import ServiceConfig, resolve_connection


@dataclass
class AppContext(AppContextBase):
    """LiteLLM-specific application context."""

    url_override: str | None = None
    _config: ServiceConfig | None = field(default=None, repr=False)

    @property
    def config(self) -> ServiceConfig:
        if self._config is None:
            self._config = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
            )
        return self._config
