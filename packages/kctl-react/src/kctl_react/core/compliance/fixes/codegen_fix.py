"""Fixer: create openapi-ts.config.ts if missing."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE = """\
import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  client: "@hey-api/client-fetch",
  input: "openapi.json",
  output: "src/generated",
  services: false,
  schemas: false,
});
"""


def fix_codegen(app_path: Path, app_name: str, dry_run: bool = False) -> int:
    """Create openapi-ts.config.ts if missing. Return count of fixes applied."""
    config_file = app_path / "openapi-ts.config.ts"
    if config_file.is_file():
        return 0

    if not dry_run:
        config_file.write_text(_TEMPLATE, encoding="utf-8")
    return 1
