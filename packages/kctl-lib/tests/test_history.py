"""Tests for kctl_lib.history."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from kctl_lib.history import HistoryStore


class TestHistoryStore:
    def _make_store(self, tmp_path: Path) -> HistoryStore:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = HistoryStore("test-cli")
            store.ensure_schema(
                [
                    """CREATE TABLE IF NOT EXISTS builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app TEXT NOT NULL,
                    size INTEGER,
                    timestamp TEXT NOT NULL
                )""",
                ]
            )
        return store

    def test_record_and_query(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = self._make_store(tmp_path)
            store.record("builds", app="portfolio", size=1024)
            rows = store.query("builds")
            assert len(rows) == 1
            assert rows[0]["app"] == "portfolio"
            assert rows[0]["size"] == 1024
            assert "timestamp" in rows[0]

    def test_query_limit(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = self._make_store(tmp_path)
            for i in range(5):
                store.record("builds", app=f"app{i}", size=i * 100)
            rows = store.query("builds", limit=3)
            assert len(rows) == 3

    def test_query_with_filter(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = self._make_store(tmp_path)
            store.record("builds", app="a", size=100)
            store.record("builds", app="b", size=200)
            rows = store.query("builds", where={"app": "a"})
            assert len(rows) == 1
            assert rows[0]["app"] == "a"

    def test_clear_table(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = self._make_store(tmp_path)
            store.record("builds", app="x", size=1)
            store.clear("builds")
            assert store.query("builds") == []

    def test_clear_all(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = self._make_store(tmp_path)
            store.record("builds", app="x", size=1)
            store.clear()
            assert store.query("builds") == []

    def test_db_path(self, tmp_path: Path) -> None:
        with patch("kctl_lib.history.DATA_BASE_DIR", tmp_path):
            store = HistoryStore("my-cli")
            expected = tmp_path / "my-cli" / "history.db"
            assert store.db_path == expected
