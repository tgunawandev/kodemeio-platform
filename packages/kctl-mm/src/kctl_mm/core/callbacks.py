"""Shared application context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_mm.core.client import MattermostClient
from kctl_mm.core.config import SERVICE_KEY, resolve_connection
from kctl_mm.core.mm_exec import MMExec


@dataclass
class AppContext(AppContextBase):
    _client: MattermostClient | None = field(default=None, repr=False, init=False)
    _mm_exec: MMExec | None = field(default=None, repr=False, init=False)
    _settings: dict | None = field(default=None, repr=False, init=False)

    @property
    def settings(self) -> dict:
        if self._settings is None:
            self._settings = resolve_connection(self.profile)
        return self._settings

    @property
    def client(self) -> MattermostClient:
        if self._client is None:
            s = self.settings
            self._client = MattermostClient(
                url=str(s["url"]),
                token=str(s["token"]),
                timeout=int(s.get("timeout", 30)),
            )
        return self._client

    @property
    def mm_exec(self) -> MMExec:
        if self._mm_exec is None:
            s = self.settings
            self._mm_exec = MMExec(
                ssh_host=str(s["ssh_host"]),
                ssh_user=str(s.get("ssh_user", "root")),
                compose_path=str(s["compose_path"]),
                compose_service=str(s.get("compose_service", "mattermost")),
            )
        return self._mm_exec

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


__all__ = ["AppContext", "SERVICE_KEY"]
