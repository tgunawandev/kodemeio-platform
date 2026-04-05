"""Load provision-config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from kctl_ak.models.provision import ProvisionConfig


def load_provision_config(path: Path) -> ProvisionConfig:
    """Load and validate provision config from YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Provision config not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid provision config: expected YAML mapping, got {type(data).__name__}")

    return ProvisionConfig(**data)
