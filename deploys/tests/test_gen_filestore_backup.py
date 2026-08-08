"""Tests for the filestore-backup instance generator.

The volume name is the whole safety story here: Dokploy names compose volumes
{appName}_{volume}, so decoy filestore volumes sit beside the live one and
picking the wrong one produces a small, successful, useless backup.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TENANT = {"code": "tpp", "name": "Pakerti", "domain": "idtpp.com"}
ENTRY = {
    "short": "erp",
    "volume": "compose-quantify-cross-platform-panel-898kcx_odoo-filestore",
    "database": "tpp_odoo_erp",
    "min_files": 36000,
    "pinned_cron": "50 2 * * *",
    "bucket": "hz-tpp-odoo-filestore",
    "server": "tpp-prod-03",
}


def test_pins_the_exact_volume_and_server():
    from generate import gen_filestore_backup

    y_name, y_content, e_name, e_content = gen_filestore_backup(TENANT, ENTRY, "production", "tpp-prod-03")

    assert y_name == "tpp-odoo-filestore-backup.yaml"
    assert "compose-quantify-cross-platform-panel-898kcx_odoo-filestore" in y_content
    assert "server: tpp-prod-03" in y_content
    assert "FILESTORE_DB: tpp_odoo_erp" in y_content
    assert "FILESTORE_MIN_FILES: '36000'" in y_content


def test_repository_url_is_scoped_per_instance():
    """Each instance gets its own restic repo prefix, so a restore or a
    compromise of one cannot reach the other."""
    from generate import gen_filestore_backup

    _, y_content, _, _ = gen_filestore_backup(TENANT, ENTRY, "production", "tpp-prod-03")

    assert "s3:https://fsn1.your-objectstorage.com/hz-tpp-odoo-filestore/tpp-odoo-erp" in y_content


def test_pinned_cron_is_carried_through():
    """The pinned run is what guarantees a filestore snapshot NEWER than the
    nightly pg_dump it will be restored alongside."""
    from generate import gen_filestore_backup

    _, y_content, _, _ = gen_filestore_backup(TENANT, ENTRY, "production", "tpp-prod-03")

    assert "BACKUP_CRON_PINNED: 50 2 * * *" in y_content


STAGING_ENTRY = {
    "short": "erp",
    "environment": "staging",
    "volume": "compose-compress-virtual-program-t5pjl6_odoo-filestore",
    "database": "tpp_odoo_erp_stg",
    "min_files": 490,
    "bucket": "hz-tpp-odoo-filestore",
    "server": "tpp-prod-07",
}


def test_staging_entry_gets_a_suffixed_name_and_its_own_repo():
    """Staging must never share a restic repository with production."""
    from generate import gen_filestore_backup

    y_name, y_content, e_name, _ = gen_filestore_backup(TENANT, STAGING_ENTRY, "staging", "tpp-prod-07", suffix="-stg")

    assert y_name == "tpp-odoo-filestore-backup-stg.yaml"
    assert "name: tpp-odoo-filestore-backup-stg" in y_content
    assert "hz-tpp-odoo-filestore/tpp-odoo-erp-stg" in y_content
    assert "FILESTORE_DB: tpp_odoo_erp_stg" in y_content
    assert "compose-compress-virtual-program-t5pjl6_odoo-filestore" in y_content
    assert e_name == ".env.tpp-odoo-filestore-backup-stg.example"


def test_staging_repo_differs_from_production_repo():
    from generate import gen_filestore_backup

    _, prod, _, _ = gen_filestore_backup(TENANT, ENTRY, "production", "tpp-prod-03")
    _, stg, _, _ = gen_filestore_backup(TENANT, STAGING_ENTRY, "staging", "tpp-prod-07", suffix="-stg")

    def repo(text):
        for line in text.splitlines():
            if "RESTIC_REPOSITORY:" in line:
                return line.split("RESTIC_REPOSITORY:", 1)[1].strip()
        raise AssertionError("no RESTIC_REPOSITORY")

    assert repo(prod) != repo(stg)


def test_env_example_never_carries_a_real_password():
    from generate import gen_filestore_backup

    _, _, e_name, e_content = gen_filestore_backup(TENANT, ENTRY, "production", "tpp-prod-03")

    assert e_name == ".env.tpp-odoo-filestore-backup.example"
    assert "RESTIC_PASSWORD=CHANGEME" in e_content
    assert "AWS_ACCESS_KEY_ID=CHANGEME" in e_content
    # the operator must be told where the real one lives
    assert "1Password" in e_content
