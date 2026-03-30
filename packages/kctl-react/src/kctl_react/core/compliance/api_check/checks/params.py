"""Query parameter validation checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation


class ParamChecker:
    name = "params"
    label = "Query Parameters"
    max_points = 5

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        for hook, operation in match.matched:
            for param in hook.query_params:
                if param not in operation.parameters:
                    violations.append(
                        Violation(
                            file=hook.file,
                            line=hook.line,
                            message=(
                                f"Unknown query param '{param}' on "
                                f"{hook.method.upper()} {hook.normalized_url} in {hook.file}"
                            ),
                            fix_hint=f"Remove '{param}' or add it to the OpenAPI schema",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
