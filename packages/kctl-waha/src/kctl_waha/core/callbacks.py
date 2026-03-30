"""Typer global callback and shared context for kctl-waha.

Subclasses AppContextBase from kctl-common, adding WAHA-specific
client resolution with X-Api-Key auth and bridge sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_waha.core.client import BridgeClient, WahaClient
from kctl_waha.core.config import resolve_bridge_url, resolve_connection


@dataclass
class AppContext(AppContextBase):
    """WAHA-specific application context."""

    url_override: str | None = None
    api_key_override: str | None = None
    bridge_url_override: str | None = None
    _client: WahaClient | None = field(default=None, repr=False)
    _bridge: BridgeClient | None = field(default=None, repr=False)

    @property
    def client(self) -> WahaClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = WahaClient(base_url=url, api_key=api_key)
        return self._client

    @property
    def bridge(self) -> BridgeClient:
        if self._bridge is None:
            bridge_url = resolve_bridge_url(
                profile_name=self.profile,
                bridge_override=self.bridge_url_override,
            )
            self._bridge = BridgeClient(base_url=bridge_url)
        return self._bridge
