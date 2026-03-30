"""Match hook API calls against OpenAPI schema operations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .hooks import HookCall
from .schema import Operation, ParsedSchema


@dataclass
class MatchResult:
    matched: list[tuple[HookCall, Operation]] = field(default_factory=list)
    orphan_endpoints: list[Operation] = field(default_factory=list)
    dead_endpoints: list[HookCall] = field(default_factory=list)


import re

_PATH_PARAM_RE = re.compile(r"\{[^}]+\}")


def _norm(path: str) -> str:
    """Normalize path for comparison: strip trailing slash, normalize path params to {id}."""
    path = path.rstrip("/")
    path = _PATH_PARAM_RE.sub("{id}", path)
    return path


def match_hooks_to_schema(hooks: list[HookCall], schema: ParsedSchema) -> MatchResult:
    """Cross-reference hook API calls against OpenAPI schema operations."""
    # Normalize schema paths for comparison
    schema_by_key: dict[tuple[str, str], Operation] = {(op.method, _norm(op.path)): op for op in schema.operations}
    hook_by_key: dict[tuple[str, str], HookCall] = {(h.method, _norm(h.normalized_url)): h for h in hooks}

    schema_keys = set(schema_by_key.keys())
    hook_keys = set(hook_by_key.keys())

    # Matched: hooks whose (method, normalized_url) matches a schema (method, path)
    matched: list[tuple[HookCall, Operation]] = []
    for key in hook_keys & schema_keys:
        matched.append((hook_by_key[key], schema_by_key[key]))

    # Orphan: schema operations not matched by any hook (GET only)
    orphan_endpoints = [
        op for op in schema.operations if op.method == "get" and (op.method, _norm(op.path)) not in hook_keys
    ]

    # Dead: hook calls not matched by any schema operation
    dead_endpoints = [h for h in hooks if (h.method, _norm(h.normalized_url)) not in schema_keys]

    return MatchResult(
        matched=matched,
        orphan_endpoints=orphan_endpoints,
        dead_endpoints=dead_endpoints,
    )
