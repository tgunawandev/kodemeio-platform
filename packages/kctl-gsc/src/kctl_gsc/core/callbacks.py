"""Typer app context for kctl-gsc."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_gsc.core.client import GSCClient
from kctl_gsc.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    profile: str | None = None
    property_override: str | None = None
    credentials_file_override: str | None = None
    _client: GSCClient | None = field(default=None, repr=False, init=False)
    _property: str | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> GSCClient:
        if self._client is None:
            creds, prop = resolve_connection(
                profile_name=self.profile,
                property_override=self.property_override,
                credentials_file_override=self.credentials_file_override,
            )
            self._client = GSCClient(credentials_file=creds)
            self._property = prop
        return self._client

    @property
    def property(self) -> str:
        if self._property is None:
            _ = self.client  # trigger resolve
        assert self._property is not None
        return self._property
