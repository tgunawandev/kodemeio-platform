"""SQLite-based history tracking for kctl-* CLI tools."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_BASE_DIR = Path.home() / ".local" / "share" / "kodemeio"


class HistoryStore:
    """SQLite-based history storage for a kctl-* CLI."""

    def __init__(self, app_name: str):
        self._app_name = app_name
        self._data_dir = DATA_BASE_DIR / app_name
        self._db_path = self._data_dir / "history.db"
        self._schema_initialized = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for safe DB connections."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def ensure_schema(self, statements: list[str]) -> None:
        """Run CREATE TABLE statements once per process."""
        if self._schema_initialized:
            return
        with self._connect() as conn:
            for stmt in statements:
                conn.execute(stmt)
            conn.commit()
        self._schema_initialized = True

    def record(self, table: str, **kwargs: Any) -> int:
        """Insert a record into a table. Adds timestamp automatically."""
        kwargs["timestamp"] = datetime.now(UTC).isoformat()
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        values = list(kwargs.values())

        with self._connect() as conn:
            cur = conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)  # noqa: S608
            conn.commit()
            return cur.lastrowid or 0

    def query(
        self,
        table: str,
        limit: int = 20,
        order_by: str = "timestamp DESC",
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query records from a table."""
        sql = f"SELECT * FROM {table}"  # noqa: S608
        params: list[Any] = []

        if where:
            clauses = [f"{k} = ?" for k in where]
            sql += " WHERE " + " AND ".join(clauses)
            params.extend(where.values())

        sql += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def clear(self, table: str | None = None) -> None:
        """Clear records from a table, or all tables if table is None."""
        with self._connect() as conn:
            if table:
                conn.execute(f"DELETE FROM {table}")  # noqa: S608
            else:
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                for row in tables:
                    conn.execute(f"DELETE FROM {row['name']}")  # noqa: S608
            conn.commit()
