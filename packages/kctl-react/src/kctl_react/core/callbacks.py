"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kctl_common.callbacks import AppContextBase

from kctl_react.core.config import resolve_project_root
from kctl_react.core.discovery import discover_apps, discover_packages


@dataclass
class AppContext(AppContextBase):
    """kctl-react application context with monorepo discovery."""

    root_override: str | None = None
    _project_root: Path | None = field(default=None, repr=False)
    _app_registry: dict[str, dict[str, Any]] | None = field(default=None, repr=False)
    _package_list: list[str] | None = field(default=None, repr=False)

    @property
    def project_root(self) -> Path:
        """Lazy-resolved monorepo root path."""
        if self._project_root is None:
            self._project_root = resolve_project_root(
                profile_name=self.profile,
                root_override=self.root_override,
            )
        return self._project_root

    @property
    def apps(self) -> dict[str, dict[str, Any]]:
        """Auto-discovered app registry from apps/ directory."""
        if self._app_registry is None:
            self._app_registry = discover_apps(self.project_root)
        return self._app_registry

    @property
    def app_names(self) -> list[str]:
        """Sorted list of discovered app names."""
        return list(self.apps.keys())

    @property
    def packages(self) -> list[str]:
        """Auto-discovered package names from packages/ directory."""
        if self._package_list is None:
            self._package_list = discover_packages(self.project_root)
        return self._package_list

    def get_framework(self, app_name: str) -> str:
        """Return framework for an app: 'vite' or 'nextjs'."""
        return self.apps.get(app_name, {}).get("framework", "vite")

    def is_nextjs(self, app_name: str) -> bool:
        """Check if an app uses Next.js."""
        return self.get_framework(app_name) == "nextjs"

    def validate_app(self, app_name: str) -> None:
        """Validate app name against discovered apps."""
        if app_name not in self.apps:
            from kctl_common.exceptions import AppNotFoundError

            raise AppNotFoundError(app_name, self.app_names)
