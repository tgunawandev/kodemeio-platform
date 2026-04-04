"""Typer global callback and shared context for kctl-mailcow.

Subclasses AppContextBase from kctl-lib, adding Mailcow-specific
client resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_mailcow.core.client import MailcowClient
from kctl_mailcow.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Mailcow-specific application context."""

    url_override: str | None = None
    api_key_override: str | None = None
    _client: MailcowClient | None = field(default=None, repr=False)

    @property
    def client(self) -> MailcowClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = MailcowClient(base_url=url, credential=api_key)
        return self._client
