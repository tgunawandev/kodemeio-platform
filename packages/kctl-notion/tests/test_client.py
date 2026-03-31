"""Tests for NotionClient."""

from __future__ import annotations

import json

import pytest
from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError

from kctl_notion.core.client import NotionClient


class TestNotionClientConstructor:
    def test_requires_credential(self):
        with pytest.raises(ConfigError):
            NotionClient()

    def test_default_base_url(self):
        client = NotionClient(credential="ntn_test")
        assert client._base_url == "https://api.notion.com/v1"
        client.close()

    def test_notion_version_header(self):
        client = NotionClient(credential="ntn_test")
        headers = client._build_auth_header()
        assert headers["Notion-Version"] == "2022-06-28"
        assert headers["Authorization"] == "Bearer ntn_test"
        client.close()

    def test_context_manager(self):
        with NotionClient(credential="ntn_test") as client:
            assert client is not None


class TestNotionClientMethods:
    def test_search(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        with NotionClient(credential="ntn_test") as client:
            result = client.search(query="meeting")
        assert result["results"][0]["object"] == "page"

    def test_search_with_filter(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        with NotionClient(credential="ntn_test") as client:
            client.search(query="test", filter_type="page")
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["filter"]["value"] == "page"

    def test_get_page(self, httpx_mock):
        page_data = {"object": "page", "id": "page-123"}
        httpx_mock.add_response(json=page_data)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_page("page-123")
        assert result["id"] == "page-123"

    def test_create_page(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "new-page-123"}, status_code=200)
        with NotionClient(credential="ntn_test") as client:
            result = client.create_page("parent-123", "Test Page")
        assert result["id"] == "new-page-123"

    def test_update_page(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "page-123"})
        with NotionClient(credential="ntn_test") as client:
            result = client.update_page("page-123", {"title": {"title": []}})
        assert result["id"] == "page-123"

    def test_get_database(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_database("db-123")
        assert result["object"] == "database"

    def test_query_database(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        with NotionClient(credential="ntn_test") as client:
            result = client.query_database("db-123")
        assert len(result["results"]) == 2

    def test_query_database_all(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        with NotionClient(credential="ntn_test") as client:
            rows = client.query_database_all("db-123")
        assert len(rows) == 2

    def test_get_block_children(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_block_children("page-123")
        assert len(result["results"]) == 2

    def test_append_block_children(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        with NotionClient(credential="ntn_test") as client:
            children = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}]
            result = client.append_block_children("page-123", children)
        assert result["object"] == "list"

    def test_list_users(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        with NotionClient(credential="ntn_test") as client:
            result = client.list_users()
        assert len(result["results"]) == 2

    def test_get_me(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_me()
        assert result["name"] == "Test Integration"


class TestNotionClientErrors:
    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"message": "API token is invalid."})
        with NotionClient(credential="bad_token") as client, pytest.raises(AuthenticationError):
            client.get("/users/me")

    def test_403_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"message": "Forbidden"})
        with NotionClient(credential="ntn_test") as client, pytest.raises(AuthenticationError):
            client.get("/pages/restricted")

    def test_404_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "Not found"})
        with NotionClient(credential="ntn_test") as client, pytest.raises(APIError) as exc_info:
            client.get("/pages/missing")
        assert exc_info.value.status_code == 404
