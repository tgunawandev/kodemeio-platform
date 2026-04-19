"""1Password secret resolution for `${op://vault/item/field}` references."""

from __future__ import annotations

import re
import subprocess

_OP_REF_RE = re.compile(r"\$\{op://([^}]+)\}")
_cache: dict[str, str] = {}


def resolve_op_refs(value: str) -> str:
    """Replace every `${op://vault/item/field}` in `value` with its resolved secret.

    Uses the `op` CLI via subprocess; results are cached for the lifetime of
    the Python process to avoid multiple round-trips for the same secret.

    Raises:
        RuntimeError: if `op read` returns a non-zero exit code.
    """

    def _replace(match: re.Match[str]) -> str:
        ref = match.group(1).strip()
        if ref in _cache:
            return _cache[ref]
        result = subprocess.run(  # noqa: S603 — trusted CLI
            ["op", "read", f"op://{ref}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to resolve `op://{ref}`: {result.stderr.strip() or 'non-zero exit'}")
        secret = result.stdout.rstrip("\n")
        _cache[ref] = secret
        return secret

    return _OP_REF_RE.sub(_replace, value)
