"""Typer global callback and shared context for kctl-sentry."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.callbacks import AppContextBase

from kctl_sentry.core.client import SentryClient
from kctl_sentry.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """kctl-sentry application context."""

    auth_token_override: str | None = None
    _client: SentryClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> SentryClient:
        if self._client is None:
            url, auth_token, organization, default_project = resolve_connection(
                profile_name=self.profile,
                auth_token_override=self.auth_token_override,
            )
            self._client = SentryClient(
                base_url=url,
                auth_token=auth_token,
                organization=organization,
                default_project=default_project,
            )
        return self._client
