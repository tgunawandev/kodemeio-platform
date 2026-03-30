"""Tests for deployment manifest Pydantic models and YAML parser."""

from __future__ import annotations

from pathlib import Path

import yaml

from kctl_dokploy.core.manifest import (
    BackupConfig,
    DatabaseConfig,
    DnsConfig,
    DomainConfig,
    HealthcheckConfig,
    InstanceConfig,
    PostDeployConfig,
    ScheduleConfig,
    SourceConfig,
    interpolate,
    load_and_resolve,
    load_manifest,
    merge_manifests,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_YAML_CONTENT = """\
kind: deploy
type: compose
source:
  type: github
  owner: kodemeio
  repo: my-app
  branch: main
  compose_path: docker-compose.yml
server: hetzner-main
project: kodemeio
instance:
  name: myapp-prod
  description: Production instance
dns:
  zone: kodeme.io
  type: A
  name: myapp
  content: 1.2.3.4
domain:
  host: myapp.kodeme.io
  port: 8000
  service: web
  https: true
  cert: letsencrypt
database:
  host: db.kodeme.io
  port: 5432
  name: myapp_prod
  user: myapp_user
healthcheck:
  path: /health
  port: 8000
  expected_status: 200
  timeout: 10
  interval: 30
env_defaults:
  APP_ENV: production
  LOG_LEVEL: info
  DEBUG: "false"
env_overrides: {}
source_overrides: {}
backup:
  destination: s3://my-bucket/backups
  type: pg_dump
  schedule: "0 2 * * *"
  prefix_template: "{instance_name}-{db_name}"
  keep_latest: 7
schedules:
  - name: daily-cleanup
    cron: "0 3 * * *"
    command: python manage.py cleanup
    service: web
    shell: /bin/sh
    timezone: UTC
post_deploy:
  odoo_profile: null
  odoo_init_db: false
"""

INSTANCE_YAML_CONTENT = """\
kind: deploy
type: compose
extends: ./base.yaml
instance:
  name: myapp-staging
  description: Staging instance
dns:
  zone: kodeme.io
  type: A
  name: myapp-staging
  content: 5.6.7.8
domain:
  host: myapp-staging.kodeme.io
  port: 8000
  service: web
  https: true
  cert: letsencrypt
database:
  host: db.kodeme.io
  port: 5432
  name: myapp_staging
  user: myapp_staging_user
env_overrides:
  APP_ENV: staging
  DEBUG: "true"
schedules:
  - name: staging-sync
    cron: "*/15 * * * *"
    command: "python manage.py sync --instance {instance_name}"
    service: web
    shell: /bin/sh
    timezone: UTC
post_deploy:
  odoo_profile: staging-profile
  odoo_init_db: true
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadBase:
    def test_load_base(self, tmp_path: Path) -> None:
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)

        manifest = load_manifest(base_file)

        # Top-level fields
        assert manifest.kind == "deploy"
        assert manifest.type == "compose"
        assert manifest.extends is None
        assert manifest.server == "hetzner-main"
        assert manifest.project == "kodemeio"

        # SourceConfig
        assert isinstance(manifest.source, SourceConfig)
        assert manifest.source.type == "github"
        assert manifest.source.owner == "kodemeio"
        assert manifest.source.repo == "my-app"
        assert manifest.source.branch == "main"
        assert manifest.source.compose_path == "docker-compose.yml"

        # InstanceConfig
        assert isinstance(manifest.instance, InstanceConfig)
        assert manifest.instance.name == "myapp-prod"
        assert manifest.instance.description == "Production instance"

        # DnsConfig
        assert isinstance(manifest.dns, DnsConfig)
        assert manifest.dns.zone == "kodeme.io"
        assert manifest.dns.type == "A"
        assert manifest.dns.name == "myapp"
        assert manifest.dns.content == "1.2.3.4"

        # DomainConfig
        assert isinstance(manifest.domain, DomainConfig)
        assert manifest.domain.host == "myapp.kodeme.io"
        assert manifest.domain.port == 8000
        assert manifest.domain.service == "web"
        assert manifest.domain.https is True
        assert manifest.domain.cert == "letsencrypt"

        # DatabaseConfig
        assert isinstance(manifest.database, DatabaseConfig)
        assert manifest.database.host == "db.kodeme.io"
        assert manifest.database.port == 5432
        assert manifest.database.name == "myapp_prod"
        assert manifest.database.user == "myapp_user"

        # HealthcheckConfig
        assert isinstance(manifest.healthcheck, HealthcheckConfig)
        assert manifest.healthcheck.path == "/health"
        assert manifest.healthcheck.port == 8000
        assert manifest.healthcheck.expected_status == 200
        assert manifest.healthcheck.timeout == 10
        assert manifest.healthcheck.interval == 30

        # env_defaults
        assert manifest.env_defaults["APP_ENV"] == "production"
        assert manifest.env_defaults["LOG_LEVEL"] == "info"
        assert manifest.env_defaults["DEBUG"] == "false"

        # env_overrides / source_overrides (empty)
        assert manifest.env_overrides == {}
        assert manifest.source_overrides == {}

        # BackupConfig
        assert isinstance(manifest.backup, BackupConfig)
        assert manifest.backup.destination == "s3://my-bucket/backups"
        assert manifest.backup.type == "pg_dump"
        assert manifest.backup.schedule == "0 2 * * *"
        assert manifest.backup.prefix_template == "{instance_name}-{db_name}"
        assert manifest.backup.keep_latest == 7

        # Schedules
        assert len(manifest.schedules) == 1
        sched = manifest.schedules[0]
        assert isinstance(sched, ScheduleConfig)
        assert sched.name == "daily-cleanup"
        assert sched.cron == "0 3 * * *"
        assert sched.command == "python manage.py cleanup"
        assert sched.service == "web"
        assert sched.shell == "/bin/sh"
        assert sched.timezone == "UTC"

        # PostDeployConfig
        assert isinstance(manifest.post_deploy, PostDeployConfig)
        assert manifest.post_deploy.odoo_profile is None
        assert manifest.post_deploy.odoo_init_db is False


class TestMergeAndResolve:
    def test_merge_base_and_instance(self, tmp_path: Path) -> None:
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)

        instance_file = tmp_path / "staging.yaml"
        instance_file.write_text(INSTANCE_YAML_CONTENT)

        result = load_and_resolve(instance_file)

        # --- Base fields inherited ---
        assert result.kind == "deploy"
        assert result.type == "compose"
        assert result.server == "hetzner-main"
        assert result.project == "kodemeio"

        # Source inherited from base
        assert result.source is not None
        assert result.source.owner == "kodemeio"
        assert result.source.repo == "my-app"
        assert result.source.branch == "main"

        # --- Instance fields override base ---
        assert result.instance.name == "myapp-staging"
        assert result.instance.description == "Staging instance"

        assert result.dns.name == "myapp-staging"
        assert result.dns.content == "5.6.7.8"

        assert result.domain.host == "myapp-staging.kodeme.io"

        assert result.database.name == "myapp_staging"
        assert result.database.user == "myapp_staging_user"

        # --- env merging: overrides applied on top of defaults ---
        assert result.env_defaults["APP_ENV"] == "production"  # base default
        assert result.env_defaults["LOG_LEVEL"] == "info"  # base default preserved
        assert result.env_overrides["APP_ENV"] == "staging"  # instance override
        assert result.env_overrides["DEBUG"] == "true"  # instance override

        # --- post_deploy overridden by instance ---
        assert result.post_deploy.odoo_profile == "staging-profile"
        assert result.post_deploy.odoo_init_db is True

        # --- Schedules replaced by instance ---
        assert len(result.schedules) == 1
        assert result.schedules[0].name == "staging-sync"

        # --- Variables interpolated in schedules ---
        assert "myapp-staging" in result.schedules[0].command

        # --- Backup prefix_template interpolated ---
        assert result.backup is not None
        assert "{instance_name}" not in result.backup.prefix_template
        assert "myapp-staging" in result.backup.prefix_template
        assert "myapp_staging" in result.backup.prefix_template

    def test_merge_manifests_env_merge(self, tmp_path: Path) -> None:
        """env_overrides merges on top of env_defaults (dict union)."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)
        base = load_manifest(base_file)

        instance_data = {
            "kind": "deploy",
            "type": "compose",
            "extends": str(base_file),
            "instance": {"name": "test-inst", "description": ""},
            "env_overrides": {"NEW_KEY": "new_val"},
        }
        instance_file = tmp_path / "inst.yaml"
        instance_file.write_text(yaml.dump(instance_data))
        instance = load_manifest(instance_file)

        merged = merge_manifests(base, instance)

        # env_defaults kept from base
        assert "APP_ENV" in merged.env_defaults
        # env_overrides accumulated
        assert merged.env_overrides["NEW_KEY"] == "new_val"

    def test_interpolate_replaces_variables(self, tmp_path: Path) -> None:
        """interpolate() replaces {instance_name}, {db_name}, {db_user}, {domain}."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)
        manifest = load_manifest(base_file)

        # Manually tweak to have all placeholders
        manifest = manifest.model_copy(
            update={
                "schedules": [
                    ScheduleConfig(
                        name="test",
                        cron="* * * * *",
                        command="run {instance_name} {db_name} {db_user} {domain}",
                        service="web",
                        shell="/bin/sh",
                        timezone="UTC",
                    )
                ],
                "backup": BackupConfig(
                    destination="s3://bucket",
                    type="pg_dump",
                    schedule="0 0 * * *",
                    prefix_template="{instance_name}-{db_name}",
                    keep_latest=3,
                ),
            }
        )

        result = interpolate(manifest)

        cmd = result.schedules[0].command
        assert "{instance_name}" not in cmd
        assert "{db_name}" not in cmd
        assert "{db_user}" not in cmd
        assert "{domain}" not in cmd
        assert "myapp-prod" in cmd
        assert "myapp_prod" in cmd
        assert "myapp_user" in cmd
        assert "myapp.kodeme.io" in cmd

        assert result.backup is not None
        assert "{instance_name}" not in result.backup.prefix_template
        assert "{db_name}" not in result.backup.prefix_template

    def test_load_manifest_without_extends(self, tmp_path: Path) -> None:
        """load_and_resolve on a base-only file (no extends) returns unchanged."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)

        result = load_and_resolve(base_file)

        assert result.instance.name == "myapp-prod"
        assert result.server == "hetzner-main"

    def test_source_overrides_patch_source(self, tmp_path: Path) -> None:
        """source_overrides on instance patches source fields."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text(BASE_YAML_CONTENT)
        base = load_manifest(base_file)

        instance_data = {
            "kind": "deploy",
            "type": "compose",
            "extends": str(base_file),
            "instance": {"name": "override-test", "description": ""},
            "source_overrides": {"branch": "develop"},
        }
        instance_file = tmp_path / "inst.yaml"
        instance_file.write_text(yaml.dump(instance_data))
        instance = load_manifest(instance_file)

        merged = merge_manifests(base, instance)

        assert merged.source is not None
        assert merged.source.branch == "develop"
        # other source fields unchanged
        assert merged.source.repo == "my-app"
