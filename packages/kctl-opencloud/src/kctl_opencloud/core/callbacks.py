"""Typer global callback and shared context for kctl-opencloud.

Subclasses AppContextBase from kctl-lib, adding OpenCloud-specific
client resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_opencloud.core.client import OpenCloudClient
from kctl_opencloud.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """OpenCloud-specific application context."""

    url_override: str | None = None
    token_override: str | None = None
    _client: OpenCloudClient | None = field(default=None, repr=False)

    @property
    def client(self) -> OpenCloudClient:
        if self._client is None:
            url, token = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                token_override=self.token_override,
            )
            self._client = OpenCloudClient(base_url=url, credential=token)
        return self._client
