"""kctl-lib: shared core library for kctl-* CLI tools.

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
    - ssh: SSH command execution (ssh_run, scp_download, scp_upload)
    - ssh_tunnel: SSHTunnel context manager for database access
"""

__version__ = "0.4.0"

from kctl_lib.api_client import APIClient
from kctl_lib.async_api_client import AsyncAPIClient
from kctl_lib.callbacks import AppContextBase
from kctl_lib.docker import DockerManager
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor
from kctl_lib.exceptions import (
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
from kctl_lib.output import Output
from kctl_lib.validate import Issue

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
    import sys

    import typer

    typer.echo(f"Error: {e}", err=True)
    # Use sys.exit rather than typer.Exit — typer.Exit is only swallowed inside
    # typer's own main(), so raising it from here bubbles up as an uncaught
    # exception and prints a Python traceback to the user.
    sys.exit(1)
