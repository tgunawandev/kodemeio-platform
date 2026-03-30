"""Select endpoints to test."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.schema import Operation, ParsedSchema


def sample_endpoints(schema: ParsedSchema, max_count: int = 20) -> list[Operation]:
    """Select GET endpoints without path parameters (list endpoints).

    These are safe to call without knowing valid IDs.
    Cap at max_count. Sort by path for deterministic order.
    """
    candidates = [op for op in schema.operations if op.method == "get" and "{" not in op.path]
    candidates.sort(key=lambda op: op.path)
    return candidates[:max_count]
