"""Tests for the api_health package (client, sampler, checkers)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kctl_react.core.compliance.api_check.schema import Operation, ParsedSchema
from kctl_react.core.compliance.api_health import EndpointResult, run_health_checks
from kctl_react.core.compliance.api_health.checks import (
    ALL_HEALTH_CHECKERS,
    CHECKER_MAP,
    AuthChecker,
    ReachableChecker,
    ResponseChecker,
    TimingChecker,
)
from kctl_react.core.compliance.api_health.client import HealthClient
from kctl_react.core.compliance.api_health.sampler import sample_endpoints


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _op(method: str, path: str, tag: str = "test") -> Operation:
    return Operation(method=method, path=path, tag=tag)


def _result(
    path: str,
    status: int = 200,
    body: dict | None = None,
    elapsed: float = 0.1,
) -> EndpointResult:
    return EndpointResult(
        operation=_op("get", path),
        status_code=status,
        body=body if body is not None else {"success": True, "data": []},
        elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_has_four_checkers(self) -> None:
        assert len(ALL_HEALTH_CHECKERS) == 4

    def test_checker_map_keys(self) -> None:
        assert set(CHECKER_MAP.keys()) == {"auth", "reachable", "response", "timing"}

    def test_checker_types(self) -> None:
        assert isinstance(CHECKER_MAP["auth"], AuthChecker)
        assert isinstance(CHECKER_MAP["reachable"], ReachableChecker)
        assert isinstance(CHECKER_MAP["response"], ResponseChecker)
        assert isinstance(CHECKER_MAP["timing"], TimingChecker)


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------


class TestSampler:
    def test_filters_get_only(self) -> None:
        schema = ParsedSchema(
            operations=[
                _op("get", "/items"),
                _op("post", "/items"),
                _op("get", "/orders"),
                _op("delete", "/items/{id}"),
            ]
        )
        result = sample_endpoints(schema)
        assert len(result) == 2
        assert all(op.method == "get" for op in result)

    def test_excludes_path_params(self) -> None:
        schema = ParsedSchema(
            operations=[
                _op("get", "/items"),
                _op("get", "/items/{id}"),
                _op("get", "/items/{id}/details"),
            ]
        )
        result = sample_endpoints(schema)
        assert len(result) == 1
        assert result[0].path == "/items"

    def test_caps_at_max_count(self) -> None:
        ops = [_op("get", f"/ep{i:03d}") for i in range(30)]
        schema = ParsedSchema(operations=ops)
        result = sample_endpoints(schema, max_count=5)
        assert len(result) == 5

    def test_sorted_by_path(self) -> None:
        schema = ParsedSchema(
            operations=[
                _op("get", "/zebra"),
                _op("get", "/alpha"),
                _op("get", "/middle"),
            ]
        )
        result = sample_endpoints(schema)
        assert [op.path for op in result] == ["/alpha", "/middle", "/zebra"]

    def test_empty_schema(self) -> None:
        schema = ParsedSchema(operations=[])
        assert sample_endpoints(schema) == []


# ---------------------------------------------------------------------------
# AuthChecker
# ---------------------------------------------------------------------------


class TestAuthChecker:
    def test_no_token_gives_violation(self) -> None:
        client = HealthClient(base_url="http://localhost:8069")
        checker = AuthChecker()
        schema = ParsedSchema()
        result = checker.check(client, schema)
        assert result.name == "auth"
        assert result.max_points == 10
        assert len(result.violations) == 1
        assert "No auth token" in result.violations[0].message

    @patch("kctl_react.core.compliance.api_health.checks.auth.HealthClient.get")
    def test_auth_me_200_valid(self, mock_get: MagicMock) -> None:
        mock_get.return_value = (200, {"success": True, "data": {"id": 1, "name": "admin"}}, 0.05)
        client = HealthClient(base_url="http://localhost:8069", token="fake-token")
        checker = AuthChecker()
        result = checker.check(client, ParsedSchema())
        assert len(result.violations) == 0
        assert result.score == 10

    @patch("kctl_react.core.compliance.api_health.checks.auth.HealthClient.get")
    def test_auth_me_non_200(self, mock_get: MagicMock) -> None:
        mock_get.return_value = (401, None, 0.05)
        client = HealthClient(base_url="http://localhost:8069", token="bad-token")
        checker = AuthChecker()
        result = checker.check(client, ParsedSchema())
        assert len(result.violations) == 1
        assert "returned 401" in result.violations[0].message

    @patch("kctl_react.core.compliance.api_health.checks.auth.HealthClient.get")
    def test_auth_me_missing_success(self, mock_get: MagicMock) -> None:
        mock_get.return_value = (200, {"data": {"id": 1}}, 0.05)
        client = HealthClient(base_url="http://localhost:8069", token="fake-token")
        checker = AuthChecker()
        result = checker.check(client, ParsedSchema())
        assert len(result.violations) == 1
        assert "missing 'success: true'" in result.violations[0].message

    @patch("kctl_react.core.compliance.api_health.checks.auth.HealthClient.get")
    def test_auth_me_missing_data(self, mock_get: MagicMock) -> None:
        mock_get.return_value = (200, {"success": True}, 0.05)
        client = HealthClient(base_url="http://localhost:8069", token="fake-token")
        checker = AuthChecker()
        result = checker.check(client, ParsedSchema())
        assert len(result.violations) == 1
        assert "missing 'data' key" in result.violations[0].message


# ---------------------------------------------------------------------------
# ReachableChecker
# ---------------------------------------------------------------------------


class TestReachableChecker:
    def test_all_200_no_violations(self) -> None:
        results = [_result("/items"), _result("/orders")]
        checker = ReachableChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 0
        assert cat.score == 10

    def test_connection_error_violation(self) -> None:
        results = [
            _result("/items"),
            EndpointResult(operation=_op("get", "/broken"), status_code=0, body=None, elapsed=0.0),
        ]
        checker = ReachableChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 1
        assert "connection error" in cat.violations[0].message

    def test_non_200_violation(self) -> None:
        results = [_result("/items", status=500, body=None)]
        checker = ReachableChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 1
        assert "returned 500" in cat.violations[0].message

    def test_mixed_results(self) -> None:
        results = [
            _result("/ok"),
            _result("/bad", status=404, body=None),
            EndpointResult(operation=_op("get", "/down"), status_code=0, body=None, elapsed=0.0),
        ]
        checker = ReachableChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 2


# ---------------------------------------------------------------------------
# ResponseChecker
# ---------------------------------------------------------------------------


class TestResponseChecker:
    def test_valid_envelope_no_violations(self) -> None:
        results = [_result("/items", body={"success": True, "data": []})]
        checker = ResponseChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 0

    def test_skips_non_200(self) -> None:
        results = [_result("/items", status=500, body=None)]
        checker = ResponseChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 0

    def test_missing_success(self) -> None:
        results = [_result("/items", body={"data": []})]
        checker = ResponseChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 1
        assert "missing 'success: true'" in cat.violations[0].message

    def test_missing_data(self) -> None:
        results = [_result("/items", body={"success": True})]
        checker = ResponseChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 1
        assert "missing 'data' key" in cat.violations[0].message

    def test_non_json_body(self) -> None:
        results = [
            EndpointResult(
                operation=_op("get", "/items"),
                status_code=200,
                body=None,
                elapsed=0.1,
            )
        ]
        checker = ResponseChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 1
        assert "non-JSON body" in cat.violations[0].message


# ---------------------------------------------------------------------------
# TimingChecker
# ---------------------------------------------------------------------------


class TestTimingChecker:
    def test_fast_responses_no_violations(self) -> None:
        results = [_result("/items", elapsed=0.5), _result("/orders", elapsed=1.0)]
        checker = TimingChecker()
        cat = checker.check(results, threshold=3.0)
        assert len(cat.violations) == 0

    def test_slow_response_violation(self) -> None:
        results = [_result("/items", elapsed=5.2)]
        checker = TimingChecker()
        cat = checker.check(results, threshold=3.0)
        assert len(cat.violations) == 1
        assert "5.2s" in cat.violations[0].message
        assert "threshold: 3.0s" in cat.violations[0].message

    def test_skips_connection_errors(self) -> None:
        results = [EndpointResult(operation=_op("get", "/down"), status_code=0, body=None, elapsed=0.0)]
        checker = TimingChecker()
        cat = checker.check(results)
        assert len(cat.violations) == 0

    def test_custom_threshold(self) -> None:
        results = [_result("/items", elapsed=1.5)]
        checker = TimingChecker()
        cat = checker.check(results, threshold=1.0)
        assert len(cat.violations) == 1


# ---------------------------------------------------------------------------
# run_health_checks
# ---------------------------------------------------------------------------


class TestRunHealthChecks:
    @patch("kctl_react.core.compliance.api_health.HealthClient.get")
    def test_calls_all_endpoints(self, mock_get: MagicMock) -> None:
        mock_get.return_value = (200, {"success": True, "data": []}, 0.1)
        client = HealthClient(base_url="http://localhost:8069", token="t")
        endpoints = [_op("get", "/a"), _op("get", "/b"), _op("get", "/c")]
        results = run_health_checks(client, endpoints)
        assert len(results) == 3
        assert mock_get.call_count == 3
        assert all(isinstance(r, EndpointResult) for r in results)


# ---------------------------------------------------------------------------
# CLI command tests (Typer CliRunner)
# ---------------------------------------------------------------------------

import json as _json
from pathlib import Path

from typer.testing import CliRunner

from kctl_react.cli import app as cli_app

_runner = CliRunner()

MINIMAL_OPENAPI: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Test", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "tags": ["test-items"],
                "responses": {
                    "200": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ItemListResponse"}}}
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "ItemListResponse": {"type": "object"},
        }
    },
}


def _add_openapi(mock_monorepo: Path, app_name: str) -> None:
    """Write a minimal openapi.json into an app directory."""
    app_dir = mock_monorepo / "apps" / app_name
    (app_dir / "openapi.json").write_text(_json.dumps(MINIMAL_OPENAPI, indent=2))


class TestApiHealthCLI:
    @patch("httpx.get")
    @patch("httpx.post")
    def test_api_health_single_app(self, mock_post: MagicMock, mock_get: MagicMock, mock_monorepo: Path) -> None:
        _add_openapi(mock_monorepo, "sfa")

        # Mock httpx.post for dev-login auth
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"success": True, "data": {"access_token": "fake-token"}}
        mock_post.return_value = mock_post_resp

        # Mock httpx.get for health check requests
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"success": True, "data": []}
        mock_get.return_value = mock_get_resp

        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "api-health", "sfa", "--token", "fake"]
        )
        assert result.exit_code == 0
        assert "Compliance Report: sfa" in result.output

    @patch("httpx.get")
    @patch("httpx.post")
    def test_api_health_json(self, mock_post: MagicMock, mock_get: MagicMock, mock_monorepo: Path) -> None:
        _add_openapi(mock_monorepo, "sfa")

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"success": True, "data": {"access_token": "fake-token"}}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"success": True, "data": []}
        mock_get.return_value = mock_get_resp

        result = _runner.invoke(
            cli_app,
            ["--json", "--root", str(mock_monorepo), "compliance", "api-health", "sfa", "--token", "fake"],
        )
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["app"] == "sfa"
        assert "categories" in data

    @patch("kctl_react.core.compliance.api_check.schema.fetch_schema", return_value=None)
    def test_api_health_no_schema(self, mock_fetch: MagicMock, mock_monorepo: Path) -> None:
        """No openapi.json should warn and exit cleanly."""
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "api-health", "sfa"])
        assert result.exit_code == 0
        assert "No OpenAPI schema" in result.output

    def test_api_health_no_app_no_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "api-health"])
        assert result.exit_code == 1
        assert "Specify an app name or use --all" in result.output
