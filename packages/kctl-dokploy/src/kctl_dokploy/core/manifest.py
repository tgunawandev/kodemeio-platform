"""Deployment manifest Pydantic models and YAML parser.

Supports base manifests, instance overrides via ``extends``, env merging,
source field patching, variable interpolation, and full load-and-resolve
pipelines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class SourceConfig(BaseModel):
    """Git source configuration."""

    type: str = "github"
    owner: str = ""
    repo: str = ""
    branch: str = "main"
    compose_path: str = "docker-compose.yml"


class InstanceConfig(BaseModel):
    """Instance identity metadata."""

    name: str = ""
    description: str = ""


class HealthcheckConfig(BaseModel):
    """HTTP healthcheck parameters."""

    path: str = "/health"
    port: int = 8000
    expected_status: int = 200
    timeout: int = 10
    interval: int = 30


class DnsConfig(BaseModel):
    """DNS record configuration."""

    zone: str = ""
    type: str = "A"
    name: str = ""
    content: str = ""


class DomainConfig(BaseModel):
    """Reverse-proxy domain/port mapping."""

    host: str = ""
    port: int = 80
    service: str = ""
    https: bool = True
    cert: str = "letsencrypt"


class DatabaseConfig(BaseModel):
    """Database connection coordinates."""

    host: str = ""
    port: int = 5432
    name: str = ""
    user: str = ""


class BackupConfig(BaseModel):
    """Backup job configuration."""

    destination: str = ""
    type: str = "pg_dump"
    schedule: str = "0 2 * * *"
    prefix_template: str = "{instance_name}-{db_name}"
    keep_latest: int = 7


class ScheduleConfig(BaseModel):
    """Scheduled task entry."""

    name: str = ""
    cron: str = ""
    command: str = ""
    service: str = ""
    shell: str = "/bin/sh"
    timezone: str = "UTC"


class PostDeployConfig(BaseModel):
    """Post-deployment actions."""

    odoo_profile: str | None = None
    commands: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level manifest
# ---------------------------------------------------------------------------


class DeployManifest(BaseModel):
    """Top-level deployment manifest."""

    kind: str = "deploy"
    type: str = "compose"
    extends: str | None = None

    source: SourceConfig = Field(default_factory=SourceConfig)
    server: str = ""
    project: str = ""
    instance: InstanceConfig = Field(default_factory=InstanceConfig)

    dns: DnsConfig = Field(default_factory=DnsConfig)
    domain: DomainConfig = Field(default_factory=DomainConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    healthcheck: HealthcheckConfig = Field(default_factory=HealthcheckConfig)

    env_file: str | None = None
    env_defaults: dict[str, str] = Field(default_factory=dict)
    env_overrides: dict[str, str] = Field(default_factory=dict)
    source_overrides: dict[str, Any] = Field(default_factory=dict)

    backup: BackupConfig | None = None
    schedules: list[ScheduleConfig] = Field(default_factory=list)
    post_deploy: PostDeployConfig = Field(default_factory=PostDeployConfig)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> DeployManifest:
    """Load a single YAML manifest file and parse it into a :class:`DeployManifest`.

    Args:
        path: Absolute or relative path to a ``.yaml`` manifest file.

    Returns:
        A fully-validated :class:`DeployManifest` instance.
    """
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    return DeployManifest.model_validate(raw)


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def _merge_submodel(base_model: BaseModel, override_model: BaseModel) -> dict[str, Any]:
    """Merge two Pydantic sub-model instances; non-default override values win."""
    base_data = base_model.model_dump()
    override_data = override_model.model_dump()
    # Use override values where they differ from the override model's defaults
    defaults = type(override_model)().model_dump()
    merged = dict(base_data)
    for key, val in override_data.items():
        if val != defaults.get(key):
            merged[key] = val
    return merged


def merge_manifests(base: DeployManifest, instance: DeployManifest) -> DeployManifest:
    """Merge a base manifest with an instance manifest.

    Rules:
    - Scalar top-level fields: instance wins if non-default.
    - Sub-models (source, dns, domain, database, healthcheck): instance wins
      field-by-field for non-default values.
    - ``env_file``: instance wins if set; base used otherwise.
    - ``env_defaults``: kept from base.
    - ``env_overrides``: instance overrides merged on top of base.
    - ``source_overrides``: applied to the resolved source fields.
    - ``schedules``: instance list replaces base list if non-empty.
    - ``post_deploy``: instance wins field-by-field for non-default values.
    - ``backup``: instance wins if not None; base used otherwise.
    - ``extends``, ``kind``, ``type``: instance wins if non-default.

    Args:
        base: The base :class:`DeployManifest`.
        instance: The instance :class:`DeployManifest` (overrides).

    Returns:
        A new merged :class:`DeployManifest`.
    """
    _empty = DeployManifest()

    def _pick(field: str) -> Any:
        inst_val = getattr(instance, field)
        base_val = getattr(base, field)
        default_val = getattr(_empty, field)
        return base_val if inst_val == default_val else inst_val

    # -- Top-level scalars --
    kind = _pick("kind")
    mtype = _pick("type")
    server = _pick("server")
    project = _pick("project")

    # -- Sub-models (field-level merge) --
    source_merged = _merge_submodel(base.source, instance.source)
    instance_merged = _merge_submodel(base.instance, instance.instance)
    dns_merged = _merge_submodel(base.dns, instance.dns)
    domain_merged = _merge_submodel(base.domain, instance.domain)
    database_merged = _merge_submodel(base.database, instance.database)
    healthcheck_merged = _merge_submodel(base.healthcheck, instance.healthcheck)
    post_deploy_merged = _merge_submodel(base.post_deploy, instance.post_deploy)

    # -- Apply source_overrides on top of merged source --
    if instance.source_overrides:
        source_merged.update(instance.source_overrides)

    # -- Env file: instance wins --
    env_file = instance.env_file or base.env_file

    # -- Env: defaults from base, overrides merged --
    env_defaults = dict(base.env_defaults)
    env_overrides = {**base.env_overrides, **instance.env_overrides}

    # -- Schedules: instance wins if non-empty --
    schedules = instance.schedules if instance.schedules else base.schedules

    # -- Backup: instance wins if set --
    backup = instance.backup if instance.backup is not None else base.backup

    return DeployManifest(
        kind=kind,
        type=mtype,
        extends=None,  # resolved manifests do not carry an extends path
        source=SourceConfig(**source_merged),
        server=server,
        project=project,
        instance=InstanceConfig(**instance_merged),
        dns=DnsConfig(**dns_merged),
        domain=DomainConfig(**domain_merged),
        database=DatabaseConfig(**database_merged),
        healthcheck=HealthcheckConfig(**healthcheck_merged),
        env_file=env_file,
        env_defaults=env_defaults,
        env_overrides=env_overrides,
        source_overrides={},
        backup=backup,
        schedules=schedules,
        post_deploy=PostDeployConfig(**post_deploy_merged),
    )


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def interpolate(manifest: DeployManifest) -> DeployManifest:
    """Replace template variables in :attr:`schedules` commands and :attr:`backup.prefix_template`.

    Supported variables:
    - ``{instance_name}`` — ``manifest.instance.name``
    - ``{db_name}`` — ``manifest.database.name``
    - ``{db_user}`` — ``manifest.database.user``
    - ``{domain}`` — ``manifest.domain.host``

    Args:
        manifest: The manifest to interpolate (not mutated).

    Returns:
        A new :class:`DeployManifest` with variables substituted.
    """
    vars_: dict[str, str] = {
        "instance_name": manifest.instance.name,
        "db_name": manifest.database.name,
        "db_user": manifest.database.user,
        "domain": manifest.domain.host,
    }

    def _sub(text: str) -> str:
        for key, value in vars_.items():
            text = text.replace(f"{{{key}}}", value)
        return text

    new_schedules = [
        sched.model_copy(update={"name": _sub(sched.name), "command": _sub(sched.command)})
        for sched in manifest.schedules
    ]

    new_backup: BackupConfig | None = None
    if manifest.backup is not None:
        new_backup = manifest.backup.model_copy(update={"prefix_template": _sub(manifest.backup.prefix_template)})

    return manifest.model_copy(
        update={
            "schedules": new_schedules,
            "backup": new_backup,
        }
    )


# ---------------------------------------------------------------------------
# Env file loading
# ---------------------------------------------------------------------------


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv-style file into a ``{key: value}`` dict.

    Ignores blank lines and ``#`` comments. Values may optionally be quoted.
    """
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes if present
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key] = value
    return env


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def load_and_resolve(instance_path: Path) -> DeployManifest:
    """Load an instance manifest, resolve its base via ``extends``, merge, and interpolate.

    If the manifest has no ``extends`` field the manifest is loaded, interpolated,
    and returned as-is.

    The ``extends`` value is resolved relative to the directory containing
    *instance_path*.

    Args:
        instance_path: Path to the instance (or standalone) manifest YAML file.

    Returns:
        A fully merged and interpolated :class:`DeployManifest`.
    """
    instance = load_manifest(instance_path)

    if not instance.extends:
        resolved = interpolate(instance)
    else:
        base_path = instance_path.parent / instance.extends
        base = load_manifest(base_path.resolve())
        merged = merge_manifests(base, instance)
        resolved = interpolate(merged)

    # Resolve env_file path relative to the instance manifest directory
    if resolved.env_file:
        env_path = (instance_path.parent / resolved.env_file).resolve()
        resolved = resolved.model_copy(update={"env_file": str(env_path)})

    return resolved
