"""Tests for blocks command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestBlocksList:
    def test_list_blocks(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "Introduction" in result.output
        assert "paragraph" in result.output

    def test_list_blocks_json(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["--json", "blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "blocks" in result.output

    def test_list_blocks_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "no blocks" in result.output.lower()


class TestBlocksAppend:
    def test_append_paragraph(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["blocks", "append", "page-123", "--text", "Hello world"])
        assert result.exit_code == 0
        assert "appended" in result.output.lower()

    def test_append_heading(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["blocks", "append", "page-123", "--text", "Title", "--type", "heading_1"])
        assert result.exit_code == 0

    def test_append_json(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["--json", "blocks", "append", "page-123", "--text", "Test"])
        assert result.exit_code == 0
