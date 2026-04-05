"""Shared test fixtures for kctl-redis."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kctl_redis.core.output import Output


class FakeRedisClient:
    """Mock Redis client for testing commands without a real connection."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._info_data: dict[str, dict[str, Any]] = {}

    def set_info(self, section: str, data: dict[str, Any]) -> None:
        """Set fake INFO data for a section."""
        self._info_data[section] = data

    def info(self, section: str | None = None) -> dict[str, Any]:
        if section:
            return self._info_data.get(section, {})
        result: dict[str, Any] = {}
        for s in self._info_data.values():
            result.update(s)
        return result

    def execute(self, *args: str) -> Any:
        return "OK"

    def ping(self) -> bool:
        return True

    @property
    def r(self) -> MagicMock:
        return MagicMock()

    @property
    def server_version(self) -> str:
        return "7.2.0"

    def close(self) -> None:
        pass


@pytest.fixture
def fake_client() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture
def output() -> Output:
    return Output(json_mode=False, quiet=False)


@pytest.fixture
def json_output() -> Output:
    return Output(json_mode=True, quiet=False)
