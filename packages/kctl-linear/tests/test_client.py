"""Tests for LinearClient."""

from __future__ import annotations

import json

import pytest

from kctl_linear.core.client import LinearClient
from kctl_linear.core.exceptions import APIError, AuthenticationError, ConfigError


class TestConstructor:
    def test_requires_api_key(self):
        with pytest.raises(ConfigError, match="API key"):
            LinearClient(api_key="")

    def test_requires_non_blank_key(self):
        with pytest.raises(ConfigError, match="API key"):
            LinearClient(api_key="   ")

    def test_creates_with_valid_key(self):
        client = LinearClient(api_key="lin_api_test123")
        assert client._api_key == "lin_api_test123"
        client.close()

    def test_context_manager(self):
        with LinearClient(api_key="lin_api_test123") as client:
            assert client is not None


class TestQuery:
    def test_successful_query(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": {"viewer": {"id": "u1", "name": "Test"}}},
        )
        with LinearClient(api_key="lin_api_test123") as client:
            result = client.query("query { viewer { id name } }")
        assert result == {"viewer": {"id": "u1", "name": "Test"}}

    def test_graphql_errors_raise_api_error(self, httpx_mock):
        httpx_mock.add_response(
            json={"errors": [{"message": "Field not found"}]},
        )
        with LinearClient(api_key="lin_api_test123") as client, pytest.raises(APIError, match="Field not found"):
            client.query("query { bad }")

    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"error": "Unauthorized"})
        with LinearClient(api_key="bad_key") as client, pytest.raises(AuthenticationError):
            client.query("query { viewer { id } }")

    def test_403_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"error": "Forbidden"})
        with LinearClient(api_key="bad_key") as client, pytest.raises(AuthenticationError):
            client.query("query { viewer { id } }")

    def test_500_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500, text="Internal Server Error")
        with LinearClient(api_key="lin_api_test123") as client, pytest.raises(APIError):
            client.query("query { viewer { id } }")

    def test_viewer_helper(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": {"viewer": {"id": "u1", "name": "Test", "email": "t@t.com", "admin": False, "active": True}}},
        )
        with LinearClient(api_key="lin_api_test123") as client:
            viewer = client.viewer()
        assert viewer["name"] == "Test"

    def test_variables_sent(self, httpx_mock):
        httpx_mock.add_response(json={"data": {"issues": {"nodes": []}}})
        with LinearClient(api_key="lin_api_test123") as client:
            client.query("query($team: String) { issues }", {"team": "KOD"})
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["variables"] == {"team": "KOD"}

    def test_auth_header_no_bearer(self, httpx_mock):
        httpx_mock.add_response(json={"data": {}})
        with LinearClient(api_key="lin_api_mykey") as client:
            client.query("query { viewer { id } }")
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "lin_api_mykey"
        assert "Bearer" not in request.headers["Authorization"]
