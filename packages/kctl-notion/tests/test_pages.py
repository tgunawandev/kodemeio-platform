"""Tests for pages command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestPagesList:
    def test_list_pages(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["pages", "list"])
        assert result.exit_code == 0
        assert "Meeting Notes" in result.output

    def test_list_pages_json(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "pages", "list"])
        assert result.exit_code == 0
        assert "pages" in result.output

    def test_list_pages_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["pages", "list"])
        assert result.exit_code == 0
        assert "no pages" in result.output.lower()


class TestPagesShow:
    def test_show_page(self, httpx_mock, mock_blocks):
        page_data = {
            "object": "page",
            "id": "page-1234-5678",
            "created_time": "2026-01-15T10:00:00.000Z",
            "last_edited_time": "2026-03-20T14:30:00.000Z",
            "parent": {"type": "workspace", "workspace": True},
            "archived": False,
            "url": "https://www.notion.so/page1234",
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}],
                }
            },
        }
        httpx_mock.add_response(json=page_data)
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["pages", "show", "page-1234-5678"])
        assert result.exit_code == 0
        assert "Test Page" in result.output

    def test_show_page_json(self, httpx_mock):
        page_data = {"object": "page", "id": "page-1234", "properties": {}}
        httpx_mock.add_response(json=page_data)
        result = runner.invoke(app, ["--json", "pages", "show", "page-1234"])
        assert result.exit_code == 0


class TestPagesCreate:
    def test_create_page(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "object": "page",
                "id": "new-page-123",
                "url": "https://www.notion.so/newpage",
            }
        )
        result = runner.invoke(app, ["pages", "create", "--parent", "parent-123", "--title", "New Page"])
        assert result.exit_code == 0
        assert "created" in result.output.lower()


class TestPagesUpdate:
    def test_update_title(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "page-123"})
        result = runner.invoke(app, ["pages", "update", "page-123", "--title", "Updated Title"])
        assert result.exit_code == 0
        assert "updated" in result.output.lower()

    def test_update_no_changes(self):
        result = runner.invoke(app, ["pages", "update", "page-123"])
        assert result.exit_code == 1
