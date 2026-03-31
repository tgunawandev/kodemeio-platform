"""Typer global callback and shared context for kctl-cf."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_cf.core.client import CloudflareClient
from kctl_cf.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    api_token_override: str | None = None
    account_id_override: str | None = None
    _client: CloudflareClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> CloudflareClient:
        if self._client is None:
            api_token, account_id = resolve_connection(
                profile_name=self.profile,
                api_token_override=self.api_token_override,
                account_id_override=self.account_id_override,
            )
            self._client = CloudflareClient(api_token=api_token, account_id=account_id)
        return self._client
