"""Tests for search command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestSearchCommand:
    def test_search_results(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["search", "meeting"])
        assert result.exit_code == 0
        assert "Meeting Notes" in result.output

    def test_search_json(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "search", "meeting"])
        assert result.exit_code == 0
        assert "results" in result.output

    def test_search_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "no results" in result.output.lower()

    def test_search_with_type_filter(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["search", "meeting", "--type", "page"])
        assert result.exit_code == 0
