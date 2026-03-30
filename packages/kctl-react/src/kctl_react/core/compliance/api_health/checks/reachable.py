"""Endpoint reachability checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_health import EndpointResult
from kctl_react.core.compliance.models import CategoryResult, Violation


class ReachableChecker:
    name = "reachable"
    label = "Endpoints Reachable"
    max_points = 10

    def check(self, results: list[EndpointResult]) -> CategoryResult:
        """Hit each sampled endpoint. Violations for non-200 responses.

        Message: "GET {path} returned {status}" or "GET {path} connection error".
        """
        violations: list[Violation] = []

        for r in results:
            if r.status_code == 0:
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} connection error",
                        fix_hint="Check that the backend is running and reachable",
                    )
                )
            elif r.status_code != 200:
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} returned {r.status_code}",
                        fix_hint="Check endpoint implementation and auth",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
