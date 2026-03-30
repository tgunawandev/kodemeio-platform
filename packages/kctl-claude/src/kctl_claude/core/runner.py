"""Safe subprocess runner for kctl-claude bash scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kctl_common.exceptions import CommandError


def run_script(
    script: Path,
    args: list[str] | None = None,
    timeout: int = 300,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a bash script with error handling.

    Args:
        script: Path to the bash script.
        args: Additional arguments to pass to the script.
        timeout: Timeout in seconds (default: 300).
        capture: Whether to capture stdout/stderr (default: True).

    Returns:
        CompletedProcess result on success.

    Raises:
        CommandError: If the script is not found, times out, or exits non-zero.
    """
    if not script.is_file():
        raise CommandError(str(script), 1, f"Script not found: {script}")

    cmd = ["bash", str(script)] + (args or [])
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CommandError(str(script), -1, f"Script timed out after {timeout}s") from e

    if result.returncode != 0:
        stderr = result.stderr if capture else ""
        raise CommandError(str(script), result.returncode, stderr)
    return result
