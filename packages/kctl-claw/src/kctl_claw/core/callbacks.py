"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kctl_lib.callbacks import AppContextBase

from kctl_claw.core.config import resolve_active_profile, resolve_project_root
from kctl_claw.core.config_manager import ConfigManager

if TYPE_CHECKING:
    from kctl_claw.core.docker_client import DockerClient
    from kctl_claw.core.gateway_client import GatewayClient


@dataclass
class AppContext(AppContextBase):
    """Shared application context passed through Typer's ctx.obj."""

    root_override: str | None = None
    live: bool = False
    _project_root: Path | None = field(default=None, repr=False)
    _config_mgr: ConfigManager | None = field(default=None, repr=False)
    _docker: object | None = field(default=None, repr=False)
    _gateway: object | None = field(default=None, repr=False)

    @property
    def project_root(self) -> Path:
        """Lazy-resolved project root path."""
        if self._project_root is None:
            resolved_profile = resolve_active_profile(self.profile)
            self._project_root = resolve_project_root(
                profile_name=resolved_profile,
                root_override=self.root_override,
            )
        return self._project_root

    @property
    def config_mgr(self) -> ConfigManager:
        """Lazy-initialized config manager."""
        if self._config_mgr is None:
            self._config_mgr = ConfigManager(self.project_root)
        return self._config_mgr

    @property
    def docker(self) -> DockerClient:
        """Lazy-initialized Docker client."""
        from kctl_claw.core.docker_client import DockerClient

        if self._docker is None:
            self._docker = DockerClient(
                compose_file=self.project_root / "docker-compose.prod.yml",
                env_file=self.project_root / ".env.prod",
            )
        assert isinstance(self._docker, DockerClient)
        return self._docker

    @property
    def gateway(self) -> GatewayClient:
        """Lazy-initialized GatewayClient."""
        from kctl_claw.core.config import get_service_config
        from kctl_claw.core.gateway_client import GatewayClient

        if self._gateway is None:
            profile = resolve_active_profile(self.profile)
            svc = get_service_config(profile)
            url = svc.gateway_url or "http://localhost:18789"
            token = svc.gateway_token or ""
            self._gateway = GatewayClient(base_url=url, token=token)
        assert isinstance(self._gateway, GatewayClient)
        return self._gateway
