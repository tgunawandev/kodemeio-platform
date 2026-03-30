"""Tests for performance optimizations."""

from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import json


class TestFieldCache:
    def test_cache_write_read(self, tmp_path):
        """Cache should persist and return cached data."""
        from kctl_odoo.core import field_helpers

        # Override cache dir
        orig_dir = field_helpers._CACHE_DIR
        field_helpers._CACHE_DIR = tmp_path / "fields"

        try:
            key = field_helpers._cache_key("http://localhost:8069", "odoo_full", "res.partner")
            fields = {"name": {"type": "char"}, "active": {"type": "boolean"}}
            field_helpers._write_cache(key, fields)

            result = field_helpers._read_cache(key)
            assert result is not None
            assert result["name"]["type"] == "char"
        finally:
            field_helpers._CACHE_DIR = orig_dir

    def test_cache_miss(self, tmp_path):
        """Cache should return None on miss."""
        from kctl_odoo.core import field_helpers

        orig_dir = field_helpers._CACHE_DIR
        field_helpers._CACHE_DIR = tmp_path / "fields"

        try:
            result = field_helpers._read_cache("nonexistent")
            assert result is None
        finally:
            field_helpers._CACHE_DIR = orig_dir

    def test_clear_cache(self, tmp_path):
        """clear_field_cache should remove all cache files."""
        from kctl_odoo.core import field_helpers

        orig_dir = field_helpers._CACHE_DIR
        field_helpers._CACHE_DIR = tmp_path / "fields"

        try:
            (tmp_path / "fields").mkdir(parents=True)
            (tmp_path / "fields" / "test.json").write_text("{}")
            count = field_helpers.clear_field_cache()
            assert count == 1
        finally:
            field_helpers._CACHE_DIR = orig_dir

    def test_get_model_fields_uses_cache(self, tmp_path):
        """get_model_fields should return cached value on second call."""
        from kctl_odoo.core import field_helpers

        orig_dir = field_helpers._CACHE_DIR
        field_helpers._CACHE_DIR = tmp_path / "fields"

        try:
            c = MagicMock()
            c._base_url = "http://localhost:8069"
            c._database = "odoo_test"
            c.execute_kw.return_value = {"name": {"type": "char"}}

            # First call — hits RPC
            result1 = field_helpers.get_model_fields(c, "res.partner")
            assert result1["name"]["type"] == "char"
            assert c.execute_kw.call_count == 1

            # Second call — hits cache, no extra RPC
            result2 = field_helpers.get_model_fields(c, "res.partner")
            assert result2["name"]["type"] == "char"
            assert c.execute_kw.call_count == 1  # still 1
        finally:
            field_helpers._CACHE_DIR = orig_dir

    def test_get_model_fields_skips_cache_when_disabled(self, tmp_path):
        """get_model_fields with use_cache=False should always call RPC."""
        from kctl_odoo.core import field_helpers

        orig_dir = field_helpers._CACHE_DIR
        field_helpers._CACHE_DIR = tmp_path / "fields"

        try:
            c = MagicMock()
            c._base_url = "http://localhost:8069"
            c._database = "odoo_test"
            c.execute_kw.return_value = {"name": {"type": "char"}}

            field_helpers.get_model_fields(c, "res.partner", use_cache=False)
            field_helpers.get_model_fields(c, "res.partner", use_cache=False)
            assert c.execute_kw.call_count == 2
        finally:
            field_helpers._CACHE_DIR = orig_dir


class TestParallelSelfTest:
    def test_import(self):
        """self_test should still import correctly."""
        from kctl_odoo.commands.self_test import SMOKE_TESTS

        assert isinstance(SMOKE_TESTS, dict)
        assert len(SMOKE_TESTS) > 50

    def test_concurrent_futures_used(self):
        """Verify the parallel implementation structure is in place."""
        import inspect
        from kctl_odoo.commands import self_test as st_module

        source = inspect.getsource(st_module)
        assert "ThreadPoolExecutor" in source
        assert "as_completed" in source


class TestClearFieldCacheCmd:
    def test_import(self):
        from kctl_odoo.commands.dev import clear_field_cache_cmd

        assert callable(clear_field_cache_cmd)
