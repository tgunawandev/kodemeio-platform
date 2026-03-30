"""Hook naming convention checker."""

from __future__ import annotations

import re

from kctl_react.core.compliance.api_check.hooks import HookCall
from kctl_react.core.compliance.api_check.matcher import MatchResult
from kctl_react.core.compliance.api_check.schema import ParsedSchema
from kctl_react.core.compliance.models import CategoryResult, Violation

_USE_PREFIX_RE = re.compile(r"use([A-Z]\w*)\.ts$")


class NamingChecker:
    name = "naming"
    label = "Hook Naming"
    max_points = 5

    def check(
        self,
        schema: ParsedSchema,
        hooks: list[HookCall],
        match: MatchResult,
    ) -> CategoryResult:
        violations: list[Violation] = []

        # Collect all tags from the schema
        tags = {op.tag.lower() for op in schema.operations}

        # Group hooks by file to avoid duplicate violations
        seen_files: set[str] = set()
        for hook in hooks:
            if hook.file in seen_files:
                continue
            seen_files.add(hook.file)

            # Extract resource name from filename
            filename = hook.file.rsplit("/", 1)[-1] if "/" in hook.file else hook.file
            m = _USE_PREFIX_RE.match(filename)
            if not m:
                continue

            resource = m.group(1).lower()

            if not any(resource in tag for tag in tags):
                violations.append(
                    Violation(
                        file=hook.file,
                        message=f"Hook {hook.file} name doesn't match any OpenAPI tag",
                        fix_hint="Rename the hook file to match a tag in the OpenAPI schema",
                    )
                )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
