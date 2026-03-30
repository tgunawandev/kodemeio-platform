"""Shared application context passed through Typer's ctx.obj."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kctl_common.callbacks import AppContextBase

from kctl_claude.core.output import Output
from kctl_claude.core.paths import resolve_paths


@dataclass
class AppContext(AppContextBase):
    """Shared application context for all kctl-claude commands.

    Extends AppContextBase with Claude-specific path resolution.
    """

    verbose: bool = False
    _output: Output | None = field(default=None, repr=False)  # type: ignore[assignment]
    _paths: dict[str, Path | None] | None = field(default=None, repr=False)

    @property
    def output(self) -> Output:  # type: ignore[override]
        if self._output is None:
            self._output = Output(
                json_mode=self.json_mode,
                quiet=self.quiet,
                format=self.format,
                no_header=self.no_header,
            )
        return self._output

    @property
    def paths(self) -> dict[str, Path | None]:
        if self._paths is None:
            self._paths = resolve_paths()
        return self._paths

    @property
    def claude_dir(self) -> Path:
        return self.paths["claude_dir"]  # type: ignore[return-value]

    @property
    def repo_dir(self) -> Path | None:
        return self.paths.get("repo_dir")

    @property
    def config_dir(self) -> Path | None:
        repo = self.repo_dir
        if repo and (repo / "config" / ".claude").is_dir():
            return repo / "config" / ".claude"
        return None
