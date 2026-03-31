"""kctl-common: shared core library for kctl-* CLI tools.

Public API:
    - exceptions: KctlError hierarchy
    - output: Output class (pretty/json/csv/yaml)
    - config: Profile/config framework
    - callbacks: AppContextBase
    - runner: run(), run_quiet(), git helpers
    - plugins: KctlPlugin protocol + discovery
    - history: HistoryStore
    - docker: DockerManager
    - validate: YAML/JSON/env/Dockerfile linting
    - git_ops: Branch status, PR, changelog, diff
    - completions: Shell completion generation
    - self_update: PyPI version check + upgrade
    - doctor_base: DoctorCheck protocol + built-in checks
    - monitor_base: Health check, SSL, DNS monitoring
    - testing: Test fixtures (optional dependency)
    - api_client: Base APIClient for httpx-based CLIs
    - async_api_client: Base AsyncAPIClient for async CLIs
"""

__version__ = "0.3.1"

from kctl_common.api_client import APIClient
from kctl_common.async_api_client import AsyncAPIClient
from kctl_common.callbacks import AppContextBase
from kctl_common.docker import DockerManager
from kctl_common.doctor_base import CheckResult, DoctorCheck, run_doctor
from kctl_common.exceptions import (
    APIError,
    AppNotFoundError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    DockerError,
    KctlError,
    NotFoundError,
    ValidationError,
)
from kctl_common.output import Output
from kctl_common.validate import Issue

__all__ = [
    "APIClient",
    "APIError",
    "AppContextBase",
    "AppNotFoundError",
    "AsyncAPIClient",
    "AuthenticationError",
    "CheckResult",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "DockerError",
    "DockerManager",
    "DoctorCheck",
    "Issue",
    "KctlError",
    "NotFoundError",
    "Output",
    "ValidationError",
    "run_doctor",
]


def handle_cli_error(e: KctlError) -> None:
    """Standardized error handler for CLI _run() entry points.

    Usage in each CLI's cli.py:
        try:
            app()
        except KctlError as e:
            handle_cli_error(e)
    """
    import typer

    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(1) from e
