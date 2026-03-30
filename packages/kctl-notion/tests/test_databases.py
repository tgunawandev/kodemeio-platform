"""Tests for databases command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestDatabasesList:
    def test_list_databases(self, httpx_mock, mock_database):
        search_result = {
            "object": "list",
            "results": [mock_database],
            "has_more": False,
        }
        httpx_mock.add_response(json=search_result)
        result = runner.invoke(app, ["databases", "list"])
        assert result.exit_code == 0
        assert "Project Tracker" in result.output

    def test_list_databases_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "list"])
        assert result.exit_code == 0
        assert "no databases" in result.output.lower()


class TestDatabasesShow:
    def test_show_database(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        result = runner.invoke(app, ["databases", "show", "db-1234"])
        assert result.exit_code == 0
        assert "Project Tracker" in result.output
        assert "Status" in result.output

    def test_show_database_json(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        result = runner.invoke(app, ["--json", "databases", "show", "db-1234"])
        assert result.exit_code == 0


class TestDatabasesQuery:
    def test_query(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "Task Alpha" in result.output

    def test_query_json(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["--json", "databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "results" in result.output

    def test_query_with_sort(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["databases", "query", "db-1234", "--sort", "Name"])
        assert result.exit_code == 0

    def test_query_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "no rows" in result.output.lower()


class TestDatabasesExport:
    def test_export_csv(self, httpx_mock, mock_database, mock_database_query_results, tmp_path):
        httpx_mock.add_response(json=mock_database_query_results)
        httpx_mock.add_response(json=mock_database)
        out_file = tmp_path / "export.csv"
        result = runner.invoke(app, ["databases", "export", "db-1234", "--output", str(out_file)])
        assert result.exit_code == 0
        assert "exported" in result.output.lower()
        assert out_file.exists()
        content = out_file.read_text()
        assert "Name" in content
        assert "Task Alpha" in content

    def test_export_json(self, httpx_mock, mock_database, mock_database_query_results, tmp_path):
        httpx_mock.add_response(json=mock_database_query_results)
        httpx_mock.add_response(json=mock_database)
        out_file = tmp_path / "export.json"
        result = runner.invoke(app, ["databases", "export", "db-1234", "--format", "json", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()

    def test_export_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "export", "db-1234"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()
