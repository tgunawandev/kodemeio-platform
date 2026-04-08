"""Server-side admin operations via SSH + docker exec.

For Zulip operations not exposed by the REST API (realm CRUD, root admin
tasks), we connect to the host running the Zulip container and run Django
shell commands inside the container.

Requires the active profile to have ssh_host configured.
"""

from __future__ import annotations

import textwrap

import typer

from kctl_lib.exceptions import KctlError
from kctl_lib.ssh import ssh_run
from kctl_zulip.core.config import ServiceConfig, get_service_config, resolve_active_profile_name


class ServerAdminError(KctlError):
    """Raised when server-side admin operation fails."""


def _resolve_ssh_config(profile: str | None) -> ServiceConfig:
    """Get the active profile's service config, ensuring SSH fields are set."""
    profile_name = resolve_active_profile_name(profile)
    cfg = get_service_config(profile_name)
    if not cfg.ssh_host:
        raise ServerAdminError(
            f"Profile '{profile_name}' has no ssh_host configured. "
            f"Run: kctl-zulip config set-ssh --host <ip> --user root"
        )
    return cfg


def docker_exec_zulip(
    cfg: ServiceConfig,
    command: str,
    timeout: int = 60,
) -> str:
    """Run a command inside the Zulip server container.

    Args:
        cfg: Service config with ssh_host etc.
        command: Shell command to run inside the container as user `zulip`.
        timeout: SSH timeout in seconds.

    Returns:
        Combined stdout from the command (stripped).

    Raises:
        ServerAdminError: If SSH or container exec fails.
    """
    # Find the Zulip server container by image filter
    container_filter = cfg.container_filter or "ancestor=zulip/docker-zulip"
    # Use shell substitution to find the container, then exec into it.
    remote_cmd = (
        f"docker exec $(docker ps --filter '{container_filter}' -q | head -1) su zulip -c {_shell_quote(command)}"
    )
    result = ssh_run(
        host=cfg.ssh_host,
        command=remote_cmd,
        user=cfg.ssh_user,
        port=cfg.ssh_port,
        ssh_key=cfg.ssh_key or None,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise ServerAdminError(f"docker exec failed (exit {result.returncode}): {result.stderr or result.stdout}")
    return result.stdout


def run_django_shell(
    profile: str | None,
    python_code: str,
    timeout: int = 60,
) -> str:
    """Run Python code in Zulip's Django shell via SSH + docker exec.

    Args:
        profile: kctl-zulip profile name (uses default if None).
        python_code: Python code to pipe to manage.py shell.
        timeout: SSH timeout in seconds.

    Returns:
        stdout from the Django shell session.
    """
    cfg = _resolve_ssh_config(profile)
    dedented = textwrap.dedent(python_code).strip()
    # We pipe Python code into manage.py shell via stdin using a heredoc.
    # The outer command (run by `su zulip -c`) reads stdin from a here-string.
    inner_cmd = f"/home/zulip/deployments/current/manage.py shell <<'PYEOF'\n{dedented}\nPYEOF"
    return docker_exec_zulip(cfg, inner_cmd, timeout=timeout)


def _shell_quote(s: str) -> str:
    """Quote a string for safe use as a single shell argument (single-quoted)."""
    return "'" + s.replace("'", "'\\''") + "'"
