"""Checker: i18n translation coverage and setup."""

from __future__ import annotations

import json
from pathlib import Path

from kctl_react.core.compliance.models import CategoryResult, Violation


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    """Flatten nested dict keys with dot notation."""
    keys: set[str] = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _flatten_keys(v, full)
        else:
            keys.add(full)
    return keys


class I18nChecker:
    name = "i18n"
    label = "Internationalization"
    max_points = 6

    def check(self, app_path: Path, app_name: str) -> CategoryResult:
        violations: list[Violation] = []
        i18n_dir = app_path / "src" / "i18n"

        en_file = i18n_dir / "en.json"
        id_file = i18n_dir / "id.json"

        if not en_file.is_file():
            violations.append(Violation(file="src/i18n/en.json", message="Missing en.json"))
        if not id_file.is_file():
            violations.append(Violation(file="src/i18n/id.json", message="Missing id.json"))

        # Key comparison
        if en_file.is_file() and id_file.is_file():
            try:
                en_data = json.loads(en_file.read_text())
                id_data = json.loads(id_file.read_text())
            except (json.JSONDecodeError, OSError):
                violations.append(
                    Violation(
                        file="src/i18n/",
                        message="Failed to parse i18n JSON files",
                    )
                )
                en_data, id_data = {}, {}

            en_keys = _flatten_keys(en_data)
            id_keys = _flatten_keys(id_data)

            missing_in_id = en_keys - id_keys
            missing_in_en = id_keys - en_keys

            for key in sorted(missing_in_id):
                violations.append(
                    Violation(
                        file="src/i18n/id.json",
                        message=f"Missing key in id.json: {key}",
                        fix_hint=f'Add "{key}" to id.json',
                        auto_fixable=True,
                    )
                )

            for key in sorted(missing_in_en):
                violations.append(
                    Violation(
                        file="src/i18n/en.json",
                        message=f"Missing key in en.json: {key}",
                        fix_hint=f'Add "{key}" to en.json',
                        auto_fixable=True,
                    )
                )

        # Check i18n/index.ts uses createI18n
        index_ts = i18n_dir / "index.ts"
        if index_ts.is_file():
            content = index_ts.read_text()
            if "createI18n" not in content:
                violations.append(
                    Violation(
                        file="src/i18n/index.ts",
                        message="i18n/index.ts does not use createI18n factory",
                        fix_hint="Use createI18n from @kodemeio/core/i18n",
                    )
                )
        else:
            violations.append(
                Violation(
                    file="src/i18n/index.ts",
                    message="Missing i18n/index.ts",
                )
            )

        return CategoryResult(
            name=self.name,
            label=self.label,
            max_points=self.max_points,
            violations=violations,
        )
