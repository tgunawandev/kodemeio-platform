"""Lazy async SQLAlchemy engine for direct database access.

Requires the ``db`` extra: ``pip install kctl-api[db]``
"""

from __future__ import annotations

import re
from typing import Any

_engines: dict[str, Any] = {}


def get_engine(database_url: str) -> Any:
    """Get or create an async engine keyed by URL.

    Raises ImportError if sqlalchemy/asyncpg are not installed.
    """
    if database_url in _engines:
        return _engines[database_url]

    try:
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError as e:
        raise ImportError("Database support requires the 'db' extra. Install with: pip install kctl-api[db]") from e

    engine = create_async_engine(
        database_url,
        pool_size=1,
        max_overflow=0,
        echo=False,
    )
    _engines[database_url] = engine
    return engine


async def dispose_engine() -> None:
    """Dispose all cached engines (call during cleanup)."""
    for engine in _engines.values():
        await engine.dispose()
    _engines.clear()


_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Validate a SQL identifier (table/column name) to prevent injection.

    Returns the name if valid, raises ValueError otherwise.
    """
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


async def execute_query(database_url: str, query: str) -> list[dict]:
    """Execute a raw SQL query and return rows as list of dicts."""
    from sqlalchemy import text

    engine = get_engine(database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(query))
        columns = list(result.keys())
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
