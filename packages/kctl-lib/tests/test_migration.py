"""Tests for kctl_lib._migration (Stage A config migration)."""

from __future__ import annotations


def test_module_importable() -> None:
    from kctl_lib import _migration

    assert hasattr(_migration, "MigrationResult")
