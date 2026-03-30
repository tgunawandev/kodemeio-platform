"""Auth validation checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.api_health.client import HealthClient
from kctl_react.core.compliance.models import CategoryResult, Violation


class AuthChecker:
    name = "auth"
    label = "Auth"
    max_points = 10

    def check(self, client: HealthClient, schema: ParsedSchema) -> CategoryResult:
        """Check /auth/me returns valid response.

        If no token and authenticate() fails -> violation.
        If /auth/me returns non-200 -> violation.
        If /auth/me response missing success/data -> violation.
        """
        violations: list[Violation] = []

        if not client.token:
            violations.append(
                Violation(
                    file="runtime",
                    message="No auth token available — dev-login failed or was not attempted",
                    fix_hint="Ensure VITE_DEV_USER/VITE_DEV_PASSWORD are set in .env or backend accepts admin/admin",
                )
            )
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        status, body, _elapsed = client.get("/auth/me")

        if status != 200:
            violations.append(
                Violation(
                    file="runtime",
                    message=f"GET /auth/me returned {status}",
                    fix_hint="Check auth token validity and /auth/me endpoint",
                )
            )
        elif body is not None:
            if not body.get("success"):
                violations.append(
                    Violation(
                        file="runtime",
                        message="GET /auth/me response missing 'success: true'",
                        fix_hint="Ensure /auth/me returns {success: true, data: ...}",
                    )
                )
            if "data" not in body:
                violations.append(
                    Violation(
                        file="runtime",
                        message="GET /auth/me response missing 'data' key",
                        fix_hint="Ensure /auth/me returns {success: true, data: ...}",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
