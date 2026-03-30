"""Shared fixtures for kctl-pg CLI tests."""

from __future__ import annotations

from typing import Any

import pytest

from kctl_pg.core.output import Output


class FakeClient:
    """Mock PostgresClient that returns pre-configured query results."""

    def __init__(self, results: dict[str, Any] | None = None):
        self._results = results or {}
        self._call_index: dict[str, int] = {}
        self.closed = False

    def add_result(self, key: str, value: Any) -> None:
        self._results[key] = value

    def fetchall(self, sql: str, params: tuple | dict | None = None) -> list[dict]:
        return self._get_result(sql)

    def fetchone(self, sql: str, params: tuple | dict | None = None) -> dict | None:
        result = self._get_result(sql)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def fetchval(self, sql: str, params: tuple | dict | None = None) -> Any:
        result = self._get_result(sql)
        if isinstance(result, list) and result:
            return next(iter(result[0].values()))
        if isinstance(result, dict):
            return next(iter(result.values()))
        return result

    def execute(self, sql: str, params: tuple | dict | None = None) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def _get_result(self, sql: str) -> Any:
        # Match by substring in the query
        for key, value in self._results.items():
            if key.lower() in sql.lower():
                return value
        return []


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def output() -> Output:
    return Output(json_mode=False, quiet=True)


@pytest.fixture
def json_output() -> Output:
    return Output(json_mode=True, quiet=False)
