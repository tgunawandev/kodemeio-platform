"""Typer global callback and shared context for kctl-api."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kctl_common.callbacks import AppContextBase

from kctl_api.core.config import resolve_connection

if TYPE_CHECKING:
    from kctl_api.core.client import ApiClient


@dataclass
class AppContext(AppContextBase):
    """API-specific application context passed through Typer's ctx.obj."""

    url_override: str | None = None
    ai_url_override: str | None = None
    api_key_override: str | None = None
    database_url_override: str | None = None
    redis_url_override: str | None = None
    _client: ApiClient | None = field(default=None, repr=False)
    _ai_client: ApiClient | None = field(default=None, repr=False)
    _db_engine: Any = field(default=None, repr=False)
    _redis_client: Any = field(default=None, repr=False)

    def _resolve(self) -> tuple[str, str, str, str, str]:
        """Resolve connection params once."""
        return resolve_connection(
            profile_name=self.profile,
            url_override=self.url_override,
            ai_url_override=self.ai_url_override,
            api_key_override=self.api_key_override,
            database_url_override=self.database_url_override,
            redis_url_override=self.redis_url_override,
        )

    @property
    def client(self) -> ApiClient:
        """Lazy API client for api-main."""
        if self._client is None:
            from kctl_api.core.client import ApiClient

            url, _ai_url, api_key, _db_url, _redis_url = self._resolve()
            self._client = ApiClient(
                base_url=url,
                api_key=api_key,
            )
        return self._client

    @property
    def ai_client(self) -> ApiClient:
        """Lazy API client for ai-main."""
        if self._ai_client is None:
            from kctl_api.core.client import ApiClient

            _url, ai_url, api_key, _db_url, _redis_url = self._resolve()
            if not ai_url:
                from kctl_api.core.exceptions import ConfigError

                raise ConfigError("No ai_url configured. Set it with: kctl-api config set ai_url <url>")
            self._ai_client = ApiClient(
                base_url=ai_url,
                api_key=api_key,
            )
        return self._ai_client

    @property
    def database_url(self) -> str:
        """Resolved database URL."""
        _url, _ai_url, _api_key, db_url, _redis_url = self._resolve()
        return db_url

    @property
    def redis_url(self) -> str:
        """Resolved Redis URL."""
        _url, _ai_url, _api_key, _db_url, redis_url = self._resolve()
        return redis_url

    def close(self) -> None:
        """Close the underlying HTTP clients if they were initialised."""
        if self._client is not None:
            self._client.close()
        if self._ai_client is not None:
            self._ai_client.close()
