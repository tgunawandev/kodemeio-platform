"""Migration manifest models for server-to-server migration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class MigrationSource(BaseModel):
    server: str
    postgres_profile: str = ""


class MigrationTarget(BaseModel):
    server: str
    postgres_profile: str = ""


class MigrationDatabase(BaseModel):
    name: str
    owner: str = "odoo"


class MigrationDns(BaseModel):
    zone: str = ""
    records: list[str] = Field(default_factory=list)


class MigrationFirewall(BaseModel):
    profile: str = ""
    required_ports: list[int] = Field(default_factory=list)


class UrlHealthCheck(BaseModel):
    type: str = "url_health"
    urls: list[str] = Field(default_factory=list)
    expected_status: list[int] = Field(default_factory=lambda: [200, 301, 303])


class DbRowCountCheck(BaseModel):
    type: str = "db_row_count"
    database: str = ""
    profile: str = ""
    tables: list[str] = Field(default_factory=list)
    match_pre: bool = False


class MigrationValidation(BaseModel):
    pre: list[dict[str, Any]] = Field(default_factory=list)
    post: list[dict[str, Any]] = Field(default_factory=list)


class MigrationCleanup(BaseModel):
    soak_hours: int = 48
    drop_source_databases: bool = True


class MigrationManifest(BaseModel):
    """Top-level migration manifest."""

    kind: str = "migration"
    name: str = ""
    description: str = ""

    source: MigrationSource
    target: MigrationTarget

    tenant: str = ""
    environment: str = "production"

    databases: list[MigrationDatabase] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)  # Paths to deploy manifests

    dns: MigrationDns = Field(default_factory=MigrationDns)
    firewall: MigrationFirewall = Field(default_factory=MigrationFirewall)
    validation: MigrationValidation = Field(default_factory=MigrationValidation)
    cleanup: MigrationCleanup = Field(default_factory=MigrationCleanup)


def load_migration_manifest(path: Path) -> MigrationManifest:
    """Load a migration YAML manifest."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return MigrationManifest(**data)
