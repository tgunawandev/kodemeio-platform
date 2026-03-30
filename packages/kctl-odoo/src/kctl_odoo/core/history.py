"""SQLite-based history tracking for Odoo operations.

Tracks module installs/updates, backups, health checks, and deployments
in a local SQLite database for auditing and trend analysis.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".local" / "share" / "kodemeio" / "kctl-odoo"
DB_PATH = DATA_DIR / "history.db"

_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS module_ops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        operation TEXT NOT NULL,
        modules TEXT NOT NULL,
        database TEXT,
        profile TEXT,
        success INTEGER NOT NULL DEFAULT 1,
        duration_s REAL
    )""",
    """CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        database TEXT NOT NULL,
        backup_type TEXT NOT NULL,
        file_path TEXT,
        size_bytes INTEGER,
        success INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS health_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        database TEXT NOT NULL,
        healthy INTEGER NOT NULL DEFAULT 1,
        version TEXT,
        active_users INTEGER,
        installed_modules INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS deployments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        database TEXT,
        profile TEXT,
        modules TEXT,
        success INTEGER NOT NULL DEFAULT 1,
        notes TEXT
    )""",
]

_schema_initialized = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Run schema migrations once per process."""
    global _schema_initialized  # noqa: PLW0603
    if _schema_initialized:
        return
    for stmt in _SCHEMA_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    _schema_initialized = True


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for safe DB connections."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        yield conn
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Module operations
# ---------------------------------------------------------------------------


def record_module_op(
    operation: str,
    modules: str,
    database: str | None = None,
    profile: str | None = None,
    success: bool = True,
    duration_s: float | None = None,
) -> int:
    """Record a module install/update/uninstall operation."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO module_ops (timestamp, operation, modules, database, profile, success, duration_s)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), operation, modules, database, profile, int(success), duration_s),
        )
        conn.commit()
        return cur.lastrowid or 0


def get_module_op_history(
    database: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve module operation history, most recent first."""
    with _connect() as conn:
        if database:
            rows = conn.execute(
                "SELECT * FROM module_ops WHERE database = ? ORDER BY timestamp DESC LIMIT ?",
                (database, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM module_ops ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


def record_backup(
    database: str,
    backup_type: str,
    file_path: str | None = None,
    size_bytes: int | None = None,
    success: bool = True,
) -> int:
    """Record a backup operation."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO backups (timestamp, database, backup_type, file_path, size_bytes, success)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), database, backup_type, file_path, size_bytes, int(success)),
        )
        conn.commit()
        return cur.lastrowid or 0


def get_backup_history(
    database: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve backup history, most recent first."""
    with _connect() as conn:
        if database:
            rows = conn.execute(
                "SELECT * FROM backups WHERE database = ? ORDER BY timestamp DESC LIMIT ?",
                (database, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM backups ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


def record_health_check(
    database: str,
    healthy: bool = True,
    version: str | None = None,
    active_users: int | None = None,
    installed_modules: int | None = None,
) -> int:
    """Record a health check result."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO health_checks (timestamp, database, healthy, version, active_users, installed_modules)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), database, int(healthy), version, active_users, installed_modules),
        )
        conn.commit()
        return cur.lastrowid or 0


def get_health_check_history(
    database: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve health check history, most recent first."""
    with _connect() as conn:
        if database:
            rows = conn.execute(
                "SELECT * FROM health_checks WHERE database = ? ORDER BY timestamp DESC LIMIT ?",
                (database, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------


def record_deployment(
    database: str | None = None,
    profile: str | None = None,
    modules: str | None = None,
    success: bool = True,
    notes: str | None = None,
) -> int:
    """Record a deployment operation."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO deployments (timestamp, database, profile, modules, success, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), database, profile, modules, int(success), notes),
        )
        conn.commit()
        return cur.lastrowid or 0


def get_deployment_history(
    database: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve deployment history, most recent first."""
    with _connect() as conn:
        if database:
            rows = conn.execute(
                "SELECT * FROM deployments WHERE database = ? ORDER BY timestamp DESC LIMIT ?",
                (database, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM deployments ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------


def clear_all_history() -> dict[str, int]:
    """Delete all rows from every history table. Returns count per table."""
    counts: dict[str, int] = {}
    with _connect() as conn:
        for table in ("module_ops", "backups", "health_checks", "deployments"):
            cur = conn.execute(f"DELETE FROM {table}")  # noqa: S608
            counts[table] = cur.rowcount
        conn.commit()
    return counts
