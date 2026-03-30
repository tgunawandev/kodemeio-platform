"""Typer global callback and shared context for kctl-telegram.

Subclasses AppContextBase from kctl-common with Telegram-specific fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_telegram.core.client import TelegramClient
from kctl_telegram.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Telegram-specific application context."""

    url_override: str | None = None
    api_key_override: str | None = None
    _client: TelegramClient | None = field(default=None, repr=False)

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = TelegramClient(base_url=url, api_key=api_key)
        return self._client
