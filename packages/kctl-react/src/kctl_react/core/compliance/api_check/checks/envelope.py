"""Response envelope conformance checker."""

from __future__ import annotations

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation


class EnvelopeChecker:
    name = "envelope"
    label = "Response Envelope"
    max_points = 5

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        for name, schema_def in schema.response_schemas.items():
            # Only check schemas that are response envelopes (end with Response)
            if not name.endswith("Response"):
                continue
            properties = schema_def.get("properties", {})
            for required_key in ("success", "data"):
                if required_key not in properties:
                    violations.append(
                        Violation(
                            file="openapi.json",
                            message=f"Schema {name} missing {required_key} in response envelope",
                            fix_hint=f"Add '{required_key}' property to {name}",
                        )
                    )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
