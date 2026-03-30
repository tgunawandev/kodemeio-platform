"""Checker: Vite configuration."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation

# Expected ports per app
APP_PORTS: dict[str, str] = {
    "sfa": "4004",
    "lfa": "4005",
    "shop": "4006",
    "wms": "4007",
    "bia": "4008",
    "eam": "4009",
    "mrp": "4010",
    "hrm": "4011",
    "tpm": "4012",
    "dms": "4013",
    "saas": "4014",
}


class ViteChecker:
    name = "vite"
    label = "Vite Config"
    max_points = 4

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []

        vite_config = app_path / "vite.config.ts"
        if not vite_config.is_file():
            violations.append(
                Violation(
                    file="vite.config.ts",
                    message="Missing vite.config.ts",
                )
            )
            return CategoryResult(
                name=self.name,
                label=self.label,
                max_points=self.max_points,
                violations=violations,
            )

        content = vite_config.read_text()

        if "createViteConfig" not in content:
            violations.append(
                Violation(
                    file="vite.config.ts",
                    message="Does not use createViteConfig from @kodemeio/vite-config",
                    fix_hint="Use createViteConfig() factory",
                )
            )

        if "@kodemeio/vite-config" not in content:
            violations.append(
                Violation(
                    file="vite.config.ts",
                    message="Does not import from @kodemeio/vite-config",
                    fix_hint="Import createViteConfig from @kodemeio/vite-config",
                )
            )

        expected_port = APP_PORTS.get(app_name)
        if expected_port and expected_port not in content:
            violations.append(
                Violation(
                    file="vite.config.ts",
                    message=f"Port {expected_port} not configured for {app_name}",
                    fix_hint=f"Set port to {expected_port} in vite config",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
