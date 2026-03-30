"""Response time checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_health import EndpointResult
from kctl_react.core.compliance.models import CategoryResult, Violation


class TimingChecker:
    name = "timing"
    label = "Response Time"
    max_points = 5

    def check(self, results: list[EndpointResult], threshold: float = 3.0) -> CategoryResult:
        """Flag endpoints slower than threshold.

        Message: "GET {path} took {elapsed:.1f}s (threshold: {threshold}s)".
        """
        violations: list[Violation] = []

        for r in results:
            if r.status_code == 0:
                continue  # connection error — already flagged by reachable
            if r.elapsed > threshold:
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} took {r.elapsed:.1f}s (threshold: {threshold}s)",
                        fix_hint="Optimize endpoint performance or increase timeout",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
