"""Request type matching checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation


class RequestChecker:
    name = "requests"
    label = "Request Types"
    max_points = 5

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        for hook, operation in match.matched:
            if operation.method not in ("post", "put", "patch"):
                continue

            if operation.request_schema and hook.request_type is None:
                violations.append(
                    Violation(
                        file=hook.file,
                        line=hook.line,
                        message=(
                            f"Missing request body type on {hook.method.upper()} {hook.normalized_url} in {hook.file}"
                        ),
                        fix_hint=f"Add request type {operation.request_schema}",
                    )
                )
            elif hook.request_type and operation.request_schema and hook.request_type != operation.request_schema:
                violations.append(
                    Violation(
                        file=hook.file,
                        line=hook.line,
                        message=(
                            f"Request type mismatch: hook uses {hook.request_type} "
                            f"but schema expects {operation.request_schema}"
                        ),
                        fix_hint=f"Change request type to {operation.request_schema}",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
