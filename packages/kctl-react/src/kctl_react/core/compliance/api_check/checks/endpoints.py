"""Endpoint coverage checker — orphan and dead endpoints."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation


class EndpointChecker:
    name = "endpoints"
    label = "Endpoint Coverage"
    max_points = 10

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        # Skip auth endpoints — handled by @kodemeio/core, not app hooks
        _SKIP_PREFIXES = ("/auth/",)

        for op in match.orphan_endpoints:
            if any(op.path.startswith(p) for p in _SKIP_PREFIXES):
                continue
            violations.append(
                Violation(
                    file="openapi.json",
                    message=f"Orphan endpoint: {op.method.upper()} {op.path} — no hook calls this",
                    fix_hint=f"Create a hook that calls {op.method.upper()} {op.path}",
                )
            )

        for hook in match.dead_endpoints:
            violations.append(
                Violation(
                    file=hook.file,
                    line=hook.line,
                    message=f"Dead endpoint: {hook.method.upper()} {hook.normalized_url} in {hook.file} — not in OpenAPI schema",
                    fix_hint="Remove this API call or add the endpoint to the OpenAPI schema",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
