"""Response envelope validation checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_health import EndpointResult
from kctl_react.core.compliance.models import CategoryResult, Violation


class ResponseChecker:
    name = "response"
    label = "Response Valid"
    max_points = 5

    def check(self, results: list[EndpointResult]) -> CategoryResult:
        """For each sampled endpoint that returned 200, check response body has {success, data}.

        Violation if success is not True or data key is missing.
        """
        violations: list[Violation] = []

        for r in results:
            if r.status_code != 200:
                continue
            if r.body is None:
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} returned non-JSON body",
                        fix_hint="Ensure endpoint returns JSON with {success, data}",
                    )
                )
                continue
            if not r.body.get("success"):
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} response missing 'success: true'",
                        fix_hint="Ensure response envelope has success: true",
                    )
                )
            if "data" not in r.body:
                violations.append(
                    Violation(
                        file="runtime",
                        message=f"GET {r.operation.path} response missing 'data' key",
                        fix_hint="Ensure response envelope has data key",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
