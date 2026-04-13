from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kctl_lib.exceptions import APIError, AuthenticationError, NotFoundError
from kctl_mm.core.client import MattermostClient


@pytest.fixture
def client() -> MattermostClient:
    return MattermostClient(url="https://mm.idtpp.com", token="tok", timeout=5)


def test_get_me_returns_user(client: MattermostClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://mm.idtpp.com/api/v4/users/me",
        json={"id": "u1", "username": "admin"},
    )
    assert client.get_me() == {"id": "u1", "username": "admin"}


def test_401_raises_auth_error(client: MattermostClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://mm.idtpp.com/api/v4/users/me",
        status_code=401,
        json={"message": "unauth"},
    )
    with pytest.raises(AuthenticationError):
        client.get_me()


def test_404_raises_not_found(client: MattermostClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://mm.idtpp.com/api/v4/users/username/ghost",
        status_code=404,
        json={"message": "not found"},
    )
    with pytest.raises(NotFoundError):
        client.get_user_by_username("ghost")


def test_500_raises_api_error(client: MattermostClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://mm.idtpp.com/api/v4/users/me",
        status_code=500,
        json={"message": "boom"},
    )
    with pytest.raises(APIError):
        client.get_me()
