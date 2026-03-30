"""Tests for health command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestHealthCommand:
    def test_health_success(self, httpx_mock, mock_notion_me, mock_search_results):
        httpx_mock.add_response(json=mock_notion_me)
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "reachable" in result.output.lower() or "healthy" in result.output.lower()

    def test_health_json(self, httpx_mock, mock_notion_me, mock_search_results):
        httpx_mock.add_response(json=mock_notion_me)
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "health"])
        assert result.exit_code == 0
        assert "healthy" in result.output
