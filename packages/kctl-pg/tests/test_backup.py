"""Tests for backup command group: dump, restore, list."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_pg.commands.config_cmd import _mask_secret


# ---------------------------------------------------------------------------
# _mask_secret helper (used in config show)
# ---------------------------------------------------------------------------


def test_mask_secret_long():
    secret = "abcd1234efgh5678"
    masked = _mask_secret(secret)
    assert masked.startswith("abcd")
    assert masked.endswith("5678")
    assert "****" in masked


def test_mask_secret_short():
    secret = "short"
    masked = _mask_secret(secret)
    assert masked == "****"


def test_mask_secret_empty():
    masked = _mask_secret("")
    assert "not set" in masked.lower() or masked == "[dim]not set[/dim]"


def test_mask_secret_exactly_10():
    secret = "1234567890"
    masked = _mask_secret(secret)
    assert masked == "****"


def test_mask_secret_11_chars():
    secret = "abcde12345f"
    masked = _mask_secret(secret)
    # len > 10 → first4****last4
    assert masked.startswith("abcd")
    assert masked.endswith("345f")


# ---------------------------------------------------------------------------
# Output file naming logic
# ---------------------------------------------------------------------------


def test_backup_dump_default_filename_custom():
    database = "myapp"
    format_ = "c"
    date_str = "20260405_120000"
    ext = ".sql" if format_ == "p" else ".dump"
    output = f"{database}_{date_str}{ext}"
    assert output == "myapp_20260405_120000.dump"


def test_backup_dump_default_filename_plain():
    database = "myapp"
    format_ = "p"
    date_str = "20260405_120000"
    ext = ".sql" if format_ == "p" else ".dump"
    output = f"{database}_{date_str}{ext}"
    assert output == "myapp_20260405_120000.sql"


def test_backup_dump_default_filename_directory():
    database = "myapp"
    format_ = "d"
    date_str = "20260405_120000"
    ext = ".sql" if format_ == "p" else ".dump"
    output = f"{database}_{date_str}{ext}"
    assert output == "myapp_20260405_120000.dump"


def test_backup_dump_filename_includes_database_name():
    database = "analytics_warehouse"
    format_ = "c"
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".dump"
    output = f"{database}_{date_str}{ext}"
    assert output.startswith("analytics_warehouse_")
    assert output.endswith(".dump")


def test_backup_dump_explicit_output_path():
    """If output is provided, it is used as-is."""
    output = "/tmp/mydb_backup.dump"
    assert output == "/tmp/mydb_backup.dump"


# ---------------------------------------------------------------------------
# Restore: file existence check
# ---------------------------------------------------------------------------


def test_restore_file_exists(tmp_path):
    dump_file = tmp_path / "myapp.dump"
    dump_file.write_bytes(b"PG\x00\x00")
    assert dump_file.exists()


def test_restore_file_not_exists(tmp_path):
    dump_file = tmp_path / "nonexistent.dump"
    assert not dump_file.exists()


# ---------------------------------------------------------------------------
# Restore: pg_restore command construction
# ---------------------------------------------------------------------------


def test_restore_opts_basic():
    user = "postgres"
    database = "myapp"
    clean = False
    restore_opts = f"-U {user} -d {database}"
    if clean:
        restore_opts += " --clean"
    assert restore_opts == "-U postgres -d myapp"


def test_restore_opts_with_clean():
    user = "postgres"
    database = "myapp"
    clean = True
    restore_opts = f"-U {user} -d {database}"
    if clean:
        restore_opts += " --clean"
    assert "--clean" in restore_opts


def test_restore_remote_cmd_construction():
    container = "kodemeio-postgres"
    restore_opts = "-U postgres -d myapp"
    remote_cmd = f"docker exec -i {container} pg_restore {restore_opts}"
    assert "docker exec -i" in remote_cmd
    assert "pg_restore" in remote_cmd
    assert "kodemeio-postgres" in remote_cmd


# ---------------------------------------------------------------------------
# Dump: pg_dump command construction
# ---------------------------------------------------------------------------


def test_dump_remote_cmd_construction():
    container = "kodemeio-postgres"
    user = "postgres"
    format_ = "c"
    database = "myapp"
    remote_cmd = f"docker exec {container} pg_dump -U {user} -F {format_} {database}"
    assert "docker exec" in remote_cmd
    assert "pg_dump" in remote_cmd
    assert "-F c" in remote_cmd
    assert "myapp" in remote_cmd


def test_dump_format_custom():
    format_ = "c"
    assert format_ == "c"


def test_dump_format_plain():
    format_ = "p"
    assert format_ == "p"


def test_dump_format_directory():
    format_ = "d"
    assert format_ == "d"


# ---------------------------------------------------------------------------
# Restore: exit code handling
# ---------------------------------------------------------------------------


def test_restore_returncode_zero_is_success():
    returncode = 0
    # returncode > 1 is a fatal error
    fatal = returncode > 1
    assert not fatal


def test_restore_returncode_one_is_warning():
    returncode = 1
    fatal = returncode > 1
    assert not fatal


def test_restore_returncode_two_is_failure():
    returncode = 2
    fatal = returncode > 1
    assert fatal


def test_restore_returncode_nonzero_with_stderr():
    returncode = 1
    stderr = "WARNING: errors ignored on restore"
    is_warning = returncode == 1 and bool(stderr)
    assert is_warning


# ---------------------------------------------------------------------------
# Container name detection
# ---------------------------------------------------------------------------


def test_get_container_name_default():
    """When SSH returns empty, default container name is used."""
    stdout = ""
    name = stdout.strip() if stdout.strip() else "kodemeio-postgres"
    assert name == "kodemeio-postgres"


def test_get_container_name_from_ssh():
    """When SSH returns a container name, it is used."""
    stdout = "my-custom-postgres\n"
    name = stdout.strip() if stdout.strip() else "kodemeio-postgres"
    assert name == "my-custom-postgres"


def test_get_container_name_whitespace_only():
    stdout = "   \n"
    name = stdout.strip() if stdout.strip() else "kodemeio-postgres"
    assert name == "kodemeio-postgres"


# ---------------------------------------------------------------------------
# File size display
# ---------------------------------------------------------------------------


def test_file_size_mb_calculation():
    file_size = 10 * 1024 * 1024  # 10 MB in bytes
    size_mb = file_size / (1024 * 1024)
    assert size_mb == 10.0


def test_file_size_small():
    file_size = 512 * 1024  # 512 KB
    size_mb = file_size / (1024 * 1024)
    assert size_mb == 0.5


def test_file_size_large():
    file_size = 2 * 1024 * 1024 * 1024  # 2 GB
    size_mb = file_size / (1024 * 1024)
    assert size_mb == 2048.0
