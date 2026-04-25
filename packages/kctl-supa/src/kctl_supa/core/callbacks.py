"""Typer global callback and shared context for kctl-supa."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_supa.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Supabase-specific application context."""

    url_override: str | None = None
    _config: object | None = field(default=None, repr=False)

    @property
    def config(self):
        if self._config is None:
            self._config = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
            )
        return self._config
