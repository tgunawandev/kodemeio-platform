"""Build history tracking — SQLite-backed via kctl-lib HistoryStore.

Provides backward-compatible API: load_history(), save_snapshot(), get_latest_snapshot().
On first use, migrates any existing .kctl-react/sizes.json to SQLite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kctl_lib.history import HistoryStore

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app TEXT,
        total_size INTEGER,
        js_size INTEGER,
        css_size INTEGER,
        asset_size INTEGER,
        page_count INTEGER,
        snapshot TEXT,
        timestamp TEXT NOT NULL
    )""",
]

_store: HistoryStore | None = None


def _get_store() -> HistoryStore:
    """Get or create the singleton HistoryStore."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = HistoryStore("kctl-react")
        _store.ensure_schema(_SCHEMA)
    return _store


def _migrate_json(root: Path) -> None:
    """One-time migration of .kctl-react/sizes.json to SQLite."""
    json_file = root / ".kctl-react" / "sizes.json"
    if not json_file.exists():
        return

    try:
        data = json.loads(json_file.read_text())
    except Exception:
        return

    if not isinstance(data, list) or not data:
        return

    store = _get_store()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        # Record each entry, using its original timestamp if present
        record_data: dict[str, Any] = {}
        record_data["app"] = entry.get("app", "")
        record_data["total_size"] = entry.get("total_size", entry.get("total_bytes", 0))
        record_data["js_size"] = entry.get("js_size", entry.get("js_bytes", 0))
        record_data["css_size"] = entry.get("css_size", entry.get("css_bytes", 0))
        record_data["asset_size"] = entry.get("asset_size", 0)
        record_data["page_count"] = entry.get("page_count", 0)
        record_data["snapshot"] = json.dumps(entry)
        store.record("builds", **record_data)

    # Rename old file as backup
    backup = json_file.with_suffix(".json.bak")
    json_file.rename(backup)


def load_history(root: Path) -> list[dict]:
    """Load build size history. Triggers migration on first call."""
    _migrate_json(root)
    store = _get_store()
    rows = store.query("builds", limit=50)
    # Reconstruct snapshot dicts for backward compat
    result = []
    for row in rows:
        if row.get("snapshot"):
            try:
                result.append(json.loads(row["snapshot"]))
            except Exception:
                result.append(dict(row))
        else:
            result.append(dict(row))
    return result


def save_snapshot(root: Path, snapshot: dict) -> None:
    """Save a build size snapshot."""
    _migrate_json(root)
    store = _get_store()
    store.record(
        "builds",
        app=snapshot.get("app", ""),
        total_size=snapshot.get("total_size", snapshot.get("total_bytes", 0)),
        js_size=snapshot.get("js_size", snapshot.get("js_bytes", 0)),
        css_size=snapshot.get("css_size", snapshot.get("css_bytes", 0)),
        asset_size=snapshot.get("asset_size", 0),
        page_count=snapshot.get("page_count", 0),
        snapshot=json.dumps(snapshot),
    )


def get_latest_snapshot(root: Path) -> dict | None:
    """Get the most recent snapshot."""
    store = _get_store()
    rows = store.query("builds", limit=1)
    if not rows:
        return None
    row = rows[0]
    if row.get("snapshot"):
        try:
            return json.loads(row["snapshot"])
        except Exception:
            return dict(row)
    return dict(row)
