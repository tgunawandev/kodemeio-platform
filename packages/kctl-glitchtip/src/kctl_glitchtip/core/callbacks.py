"""Typer global callback and shared context for kctl-glitchtip."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_glitchtip.core.client import GlitchTipClient
from kctl_glitchtip.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """kctl-glitchtip application context."""

    url_override: str | None = None
    token_override: str | None = None
    _client: GlitchTipClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> GlitchTipClient:
        if self._client is None:
            url, token = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                token_override=self.token_override,
            )
            self._client = GlitchTipClient(base_url=url, token=token)
        return self._client
