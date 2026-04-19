"""Abstract base context for kctl-* CLI tools."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from kctl_lib.output import Output, profile_banner


@dataclass
class AppContextBase:
    """Base application context with lazy Output initialization.

    Subclass in each CLI to add domain-specific properties:
    - Monorepo CLIs (next, react): project_root, apps, packages, validate_app()
    - Server CLIs (odoo, api): url_override, api_key_override, client
    - Claw: root_override, live, docker, gateway, config_mgr
    """

    json_mode: bool = False
    quiet: bool = False
    profile: str | None = None
    format: str = "pretty"
    no_header: bool = False
    _output: Output | None = field(default=None, repr=False)
    _banner_emitted: bool = field(default=False, repr=False)

    @property
    def output(self) -> Output:
        """Lazy-initialized output handler."""
        if self._output is None:
            self._output = Output(
                json_mode=self.json_mode,
                quiet=self.quiet,
                format=self.format,
                no_header=self.no_header,
            )
        return self._output

    def emit_banner(
        self,
        app: str,
        inheritance_chain: list[str],
        service_summary: str | None,
    ) -> None:
        """Emit the profile banner to stderr, exactly once.

        Suppressed in `--quiet` and `--json` modes. JSON callers should embed
        `_profile` in their stdout JSON body instead.
        """
        if self._banner_emitted or self.quiet or self.json_mode:
            return
        if not self.profile:
            return
        text = profile_banner(
            app=app,
            profile=self.profile,
            inheritance_chain=inheritance_chain,
            service_summary=service_summary,
        )
        sys.stderr.write(text)
        self._banner_emitted = True
