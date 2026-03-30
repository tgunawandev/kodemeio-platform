"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_grafana.core.client import GrafanaClient
from kctl_grafana.core.config import resolve_connection
from kctl_grafana.core.output import Output


@dataclass
class AppContext:
    """Shared application context passed through Typer's ctx.obj."""

    json_mode: bool = False
    quiet: bool = False
    format: str = "pretty"
    no_header: bool = False
    debug: bool = False
    profile: str | None = None
    url_override: str | None = None
    api_key_override: str | None = None
    _client: GrafanaClient | None = field(default=None, repr=False, init=False)
    _output: Output | None = field(default=None, repr=False, init=False)

    @property
    def output(self) -> Output:
        if self._output is None:
            self._output = Output(
                json_mode=self.json_mode,
                quiet=self.quiet,
                format=self.format,
                no_header=self.no_header,
            )
        return self._output

    @property
    def client(self) -> GrafanaClient:
        if self._client is None:
            url, api_key, org_id = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = GrafanaClient(base_url=url, api_key=api_key, org_id=org_id)
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client is not None:
            self._client.close()
