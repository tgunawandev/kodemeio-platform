"""Typer global callback and shared context.

# KCTL-COMMON: extractable
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_outline.core.client import OutlineClient
from kctl_outline.core.config import resolve_connection
from kctl_outline.core.output import Output


@dataclass
class AppContext:
    """Shared application context passed through Typer's ctx.obj."""

    json_mode: bool = False
    quiet: bool = False
    profile: str | None = None
    url_override: str | None = None
    token_override: str | None = None
    _client: OutlineClient | None = field(default=None, repr=False)
    _output: Output | None = field(default=None, repr=False)

    @property
    def output(self) -> Output:
        if self._output is None:
            self._output = Output(json_mode=self.json_mode, quiet=self.quiet)
        return self._output

    @property
    def client(self) -> OutlineClient:
        if self._client is None:
            url, token = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                token_override=self.token_override,
            )
            self._client = OutlineClient(base_url=url, token=token)
        return self._client
