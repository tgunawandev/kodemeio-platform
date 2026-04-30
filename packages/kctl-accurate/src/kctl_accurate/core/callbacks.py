"""Typer global callback context for kctl-accurate.

Subclass of AppContextBase that adds Accurate-specific override fields
and lazy-initializes the AccurateClientWrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_accurate.core.client import AccurateClientWrapper
from kctl_accurate.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):  # type: ignore[misc]
    """kctl-accurate application context."""

    api_token_override: str | None = None
    signature_secret_override: str | None = None
    db_id_override: int | None = None
    host_override: str | None = None
    _client: AccurateClientWrapper | None = field(default=None, repr=False)

    @property
    def client(self) -> AccurateClientWrapper:
        if self._client is None:
            cfg = resolve_connection(
                profile_name=self.profile,
                api_token_override=self.api_token_override,
                signature_secret_override=self.signature_secret_override,
                db_id_override=self.db_id_override,
                host_override=self.host_override,
            )
            self._client = AccurateClientWrapper(cfg)
        return self._client
