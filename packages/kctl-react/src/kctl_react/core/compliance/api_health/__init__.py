"""API health: runtime endpoint validation."""

from __future__ import annotations

from dataclasses import dataclass

from kctl_react.core.compliance.api_check.schema import Operation

from .client import HealthClient


@dataclass
class EndpointResult:
    """Result of hitting a single endpoint."""

    operation: Operation
    status_code: int
    body: dict | None
    elapsed: float


def run_health_checks(client: HealthClient, endpoints: list[Operation]) -> list[EndpointResult]:
    """Hit each endpoint once, return results for all checkers to use."""
    results: list[EndpointResult] = []
    for op in endpoints:
        status, body, elapsed = client.get(op.path)
        results.append(
            EndpointResult(
                operation=op,
                status_code=status,
                body=body,
                elapsed=elapsed,
            )
        )
    return results
