"""Application context for kctl-notion."""

from __future__ import annotations

from dataclasses import dataclass

from kctl_common.callbacks import AppContextBase

from kctl_notion.core.client import NotionClient
from kctl_notion.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)


@dataclass
class AppContext(AppContextBase):
    """kctl-notion application context."""

    _client: NotionClient | None = None

    def get_client(self) -> NotionClient:
        """Get or create a NotionClient from the active profile."""
        if self._client is None:
            profile = resolve_active_profile_name(self.profile)
            svc: ServiceConfig = get_service_config(profile)
            self._client = NotionClient(credential=svc.token)
        return self._client

    def close(self) -> None:
        """Close the client if open."""
        if self._client is not None:
            self._client.close()
            self._client = None
