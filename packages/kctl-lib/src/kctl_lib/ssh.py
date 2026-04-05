"""Standardized SSH command execution for kctl-* CLIs.

Provides ssh_run() for remote command execution and scp_download()/scp_upload()
for file transfers. All functions use consistent timeout, error handling, and
StrictHostKeyChecking settings.

Usage:
    from kctl_lib.ssh import ssh_run, scp_download, scp_upload

    result = ssh_run("91.98.80.207", "docker ps", user="root")
    scp_download("91.98.80.207", "/data/dump.rdb", "./dump.rdb")
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from kctl_lib.exceptions import KctlError


@dataclass
class SSHResult:
    """Result from an SSH command execution."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class SSHCommandError(KctlError):
    """SSH remote command failed."""

    def __init__(self, host: str, command: str, returncode: int, stderr: str = ""):
        self.host = host
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"SSH command failed on {host}: {command}\nExit code: {returncode}\nstderr: {stderr}")


def _build_ssh_base(
    host: str,
    user: str = "root",
    port: int = 22,
    ssh_key: str | None = None,
    timeout: int = 10,
) -> list[str]:
    """Build base SSH command with standard options."""
    cmd = [
        "ssh",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "BatchMode=yes",
        "-p",
        str(port),
    ]
    if ssh_key:
        key_path = str(Path(ssh_key).expanduser())
        cmd.extend(["-i", key_path])
    cmd.append(f"{user}@{host}")
    return cmd


def ssh_run(
    host: str,
    command: str,
    user: str = "root",
    port: int = 22,
    ssh_key: str | None = None,
    timeout: int = 30,
    connect_timeout: int = 10,
    check: bool = False,
    capture: bool = True,
) -> SSHResult:
    """Execute a command on a remote host via SSH.

    Args:
        host: Remote hostname or IP.
        command: Command string to execute.
        user: SSH username (default: root).
        port: SSH port (default: 22).
        ssh_key: Path to SSH private key (optional).
        timeout: Overall command timeout in seconds.
        connect_timeout: SSH connection timeout in seconds.
        check: If True, raise SSHCommandError on non-zero exit.
        capture: If True, capture stdout/stderr (default). False streams to terminal.

    Returns:
        SSHResult with returncode, stdout, stderr.

    Raises:
        KctlConnectionError: On SSH connection timeout.
        SSHCommandError: On non-zero exit if check=True.
    """
    cmd = _build_ssh_base(host, user, port, ssh_key, connect_timeout)
    cmd.append(command)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise KctlConnectionError(
            f"{user}@{host}:{port}",
            TimeoutError(f"SSH timed out after {timeout}s"),
        ) from e
    except FileNotFoundError as e:
        raise KctlConnectionError(
            f"{user}@{host}:{port}",
            e,
        ) from e

    result = SSHResult(
        returncode=proc.returncode,
        stdout=proc.stdout.strip() if capture else "",
        stderr=proc.stderr.strip() if capture else "",
    )

    if check and not result.ok:
        raise SSHCommandError(
            host=host,
            command=command,
            returncode=result.returncode,
            stderr=result.stderr,
        )

    return result


def scp_download(
    host: str,
    remote_path: str,
    local_path: str,
    user: str = "root",
    port: int = 22,
    ssh_key: str | None = None,
    timeout: int = 300,
) -> None:
    """Download a file from a remote host via SCP.

    Raises:
        KctlConnectionError: On timeout.
        SSHCommandError: On transfer failure.
    """
    cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-P", str(port)]
    if ssh_key:
        cmd.extend(["-i", str(Path(ssh_key).expanduser())])
    cmd.append(f"{user}@{host}:{remote_path}")
    cmd.append(local_path)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise KctlConnectionError(
            f"{user}@{host}:{port}",
            TimeoutError(f"SCP download timed out after {timeout}s"),
        ) from e

    if proc.returncode != 0:
        raise SSHCommandError(
            host=host,
            command=f"scp {remote_path} -> {local_path}",
            returncode=proc.returncode,
            stderr=proc.stderr.strip(),
        )


def scp_upload(
    host: str,
    local_path: str,
    remote_path: str,
    user: str = "root",
    port: int = 22,
    ssh_key: str | None = None,
    timeout: int = 300,
) -> None:
    """Upload a file to a remote host via SCP.

    Raises:
        KctlConnectionError: On timeout.
        SSHCommandError: On transfer failure.
    """
    cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-P", str(port)]
    if ssh_key:
        cmd.extend(["-i", str(Path(ssh_key).expanduser())])
    cmd.append(local_path)
    cmd.append(f"{user}@{host}:{remote_path}")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise KctlConnectionError(
            f"{user}@{host}:{port}",
            TimeoutError(f"SCP upload timed out after {timeout}s"),
        ) from e

    if proc.returncode != 0:
        raise SSHCommandError(
            host=host,
            command=f"scp {local_path} -> {remote_path}",
            returncode=proc.returncode,
            stderr=proc.stderr.strip(),
        )
