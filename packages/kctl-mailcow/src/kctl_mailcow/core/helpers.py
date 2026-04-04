"""Shared helpers for kctl-mailcow commands."""

from __future__ import annotations

from typing import Any

import typer

from kctl_mailcow.core.callbacks import AppContext


def handle_result(c: AppContext, result: Any, success_msg: str) -> None:
    """Handle Mailcow API mutation result.

    Mailcow returns ``[{type, log, msg}]`` arrays for mutations.
    Type "danger" indicates an error.
    """
    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
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
