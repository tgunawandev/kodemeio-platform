"""Abstract base context for kctl-* CLI tools."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_common.output import Output


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
