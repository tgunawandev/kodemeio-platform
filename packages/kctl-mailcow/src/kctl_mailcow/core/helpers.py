"""Shared helpers for kctl-mailcow commands."""

from __future__ import annotations

from typing import Any

import typer

from kctl_mailcow.core.callbacks import AppContext


def _format_error_msg(msg: Any) -> str:
    """Translate known Mailcow error codes into actionable human messages.

    Mailcow often returns ``msg`` as a list like ``['mailbox_quota_left_exceeded', 68]``
    where the second element is the number of MB left. Render those clearly.
    """
    if isinstance(msg, list) and msg:
        code = str(msg[0])
        detail = msg[1] if len(msg) > 1 else None
        known = {
            "mailbox_quota_left_exceeded": (
                f"Domain quota exceeded -- only {detail} MB left for the domain. "
                f"Bump the domain quota first (e.g. `kctl-mailcow domains update <domain> --quota <bytes>`) "
                f"or pass `--expand-domain-quota` to `mailboxes add` to do it automatically."
            ),
            "object_exists": f"Object already exists: {detail}",
            "domain_quota_exceeded_scope_mailbox": (f"Per-mailbox quota exceeds the domain's maxquota ({detail})."),
            "max_quota_in_domain": (f"Requested quota is above the domain's per-mailbox maximum ({detail} MB)."),
        }
        if code in known:
            return known[code]
        if detail is not None:
            return f"{code}: {detail}"
        return code
    return str(msg)


def handle_result(c: AppContext, result: Any, success_msg: str) -> None:
    """Handle Mailcow API mutation result.

    Mailcow returns ``[{type, log, msg}]`` arrays for mutations.
    Type "danger" indicates an error.
    """
    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(_format_error_msg(e.get("msg", e)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    elif isinstance(result, dict):
        if result.get("type") == "danger":
            c.output.error(str(result.get("msg", result)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    else:
        c.output.success(success_msg)
