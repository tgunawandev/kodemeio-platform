"""Response type matching checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation


class TypeChecker:
    name = "types"
    label = "Response Types"
    max_points = 10

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        for hook, operation in match.matched:
            if hook.response_type is None:
                violations.append(
                    Violation(
                        file=hook.file,
                        line=hook.line,
                        message=(
                            f"Missing response type generic on "
                            f"{hook.method.upper()} {hook.normalized_url} in {hook.file}"
                        ),
                        fix_hint="Add a response type generic to the API call",
                    )
                )
            elif operation.response_schema and hook.response_type != operation.response_schema:
                violations.append(
                    Violation(
                        file=hook.file,
                        line=hook.line,
                        message=(
                            f"Type mismatch: hook uses {hook.response_type} "
                            f"but schema expects {operation.response_schema}"
                        ),
                        fix_hint=f"Change response type to {operation.response_schema}",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
