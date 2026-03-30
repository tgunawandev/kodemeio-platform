"""Fixer: sync missing i18n keys between en.json and id.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _flatten_keys(d: dict[str, Any], prefix: str = "") -> set[str]:
    """Flatten nested dict keys to dot notation."""
    keys: set[str] = set()
    for k, v in d.items():
        full = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            keys.update(_flatten_keys(v, full))
        else:
            keys.add(full)
    return keys


def _set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a nested key using dot notation, creating intermediate dicts."""
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def fix_i18n(app_path: Path, app_name: str, dry_run: bool = False) -> int:
    """Add missing keys (as empty strings) to en.json / id.json. Return fix count."""
    i18n_dir = app_path / "src" / "i18n"
    en_path = i18n_dir / "en.json"
    id_path = i18n_dir / "id.json"

    if not en_path.is_file() or not id_path.is_file():
        return 0

    en_data: dict[str, Any] = json.loads(en_path.read_text(encoding="utf-8"))
    id_data: dict[str, Any] = json.loads(id_path.read_text(encoding="utf-8"))

    en_keys = _flatten_keys(en_data)
    id_keys = _flatten_keys(id_data)

    count = 0

    # Keys in en but missing in id
    for key in sorted(en_keys - id_keys):
        _set_nested(id_data, key, "")
        count += 1

    # Keys in id but missing in en
    for key in sorted(id_keys - en_keys):
        _set_nested(en_data, key, "")
        count += 1

    if count > 0 and not dry_run:
        en_path.write_text(json.dumps(en_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        id_path.write_text(json.dumps(id_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return count
