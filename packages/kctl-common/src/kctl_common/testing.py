"""Shared test fixtures and helpers for kctl-* CLI test suites.

Install via: kctl-common[testing]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kctl_common.callbacks import AppContextBase
from kctl_common.output import Output


def mock_output(**overrides: Any) -> Output:
    """Create an Output instance in JSON mode for test assertions."""
    defaults = {"json_mode": True, "quiet": False, "format": "json", "no_header": False}
    defaults.update(overrides)
    return Output(**defaults)


def mock_app_context(**overrides: Any) -> AppContextBase:
    """Create a pre-configured AppContextBase for tests."""
    return AppContextBase(**overrides)


def temp_config(profiles: dict[str, Any], base_dir: Path | None = None) -> Path:
    """Write a temporary config.yaml and return its path."""
    if base_dir is None:
        import tempfile

        base_dir = Path(tempfile.mkdtemp())

    config_file = base_dir / "config.yaml"
    data = {"default_profile": "default", "profiles": profiles}
    with open(config_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return config_file
