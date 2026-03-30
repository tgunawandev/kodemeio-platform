"""Tests for the api_check package (schema, hooks, matcher)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kctl_react.core.compliance.api_check.hooks import HookCall, parse_hooks
from kctl_react.core.compliance.api_check.matcher import MatchResult, match_hooks_to_schema
from kctl_react.core.compliance.api_check.schema import (
    Operation,
    ParsedSchema,
    load_schema,
    parse_schema,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_OPENAPI: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Test", "version": "1.0.0"},
    "paths": {
        "/productions": {
            "get": {
                "tags": ["mrp-productions"],
                "parameters": [
                    {"name": "state", "in": "query"},
                    {"name": "search", "in": "query"},
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/ProductionListResponse"}}
                        }
                    }
                },
            }
        },
        "/productions/{id}": {
            "get": {
                "tags": ["mrp-productions"],
                "parameters": [{"name": "id", "in": "path"}],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/ProductionDetailResponse"}}
                        }
                    }
                },
            },
            "put": {
                "tags": ["mrp-productions"],
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/UpdateProductionRequest"}}
                    }
                },
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/ProductionDetailResponse"}}
                        }
                    }
                },
            },
        },
        "/reports/summary": {
            "get": {
                "tags": ["mrp-reports"],
                "responses": {
                    "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ReportSummary"}}}}
                },
            }
        },
    },
    "components": {
        "schemas": {
            "ProductionListResponse": {"type": "object"},
            "ProductionDetailResponse": {"type": "object"},
            "UpdateProductionRequest": {"type": "object"},
            "ReportSummary": {"type": "object"},
        }
    },
}

HOOK_FILE_CONTENT = """\
import { apiClient } from "./client";

export function useProductions() {
  return apiClient.get<ProductionListResponse>("/productions");
}

export function useProductionDetail(id: number) {
  return apiClient.get<ProductionDetailResponse>(`/productions/${id}`);
}

export function useUpdateProduction(id: number) {
  return apiClient.put<ProductionDetailResponse, UpdateProductionRequest>(`/productions/${id}`);
}

export function useDeleteProduction(id: number) {
  return apiClient.delete<void>(`/productions/${id}`);
}
"""


# ---------------------------------------------------------------------------
# Tests: parse_schema
# ---------------------------------------------------------------------------


class TestParseSchema:
    def test_parses_operations(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        assert isinstance(result, ParsedSchema)
        assert len(result.operations) == 4  # 2 GET + 1 PUT + 1 GET (reports)

    def test_extracts_tags(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        tags = {op.tag for op in result.operations}
        assert "mrp-productions" in tags
        assert "mrp-reports" in tags

    def test_extracts_response_schema(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        get_list = next(op for op in result.operations if op.path == "/productions" and op.method == "get")
        assert get_list.response_schema == "ProductionListResponse"

    def test_extracts_request_schema(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        put_op = next(op for op in result.operations if op.method == "put")
        assert put_op.request_schema == "UpdateProductionRequest"

    def test_extracts_parameters(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        get_list = next(op for op in result.operations if op.path == "/productions" and op.method == "get")
        assert "state" in get_list.parameters
        assert "search" in get_list.parameters

    def test_extracts_component_schemas(self) -> None:
        result = parse_schema(MINIMAL_OPENAPI)
        assert "ProductionListResponse" in result.response_schemas
        assert "ReportSummary" in result.response_schemas

    def test_empty_paths(self) -> None:
        result = parse_schema({"paths": {}})
        assert result.operations == []
        assert result.response_schemas == {}


# ---------------------------------------------------------------------------
# Tests: parse_hooks
# ---------------------------------------------------------------------------


class TestParseHooks:
    def test_parses_api_calls(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "useProductions.ts").write_text(HOOK_FILE_CONTENT)

        results = parse_hooks(tmp_path)
        assert len(results) == 4  # get, get, put, delete

    def test_normalizes_template_urls(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "useProductions.ts").write_text(HOOK_FILE_CONTENT)

        results = parse_hooks(tmp_path)
        detail_call = next(r for r in results if r.method == "get" and "${" in r.url)
        assert detail_call.normalized_url == "/productions/{id}"

    def test_extracts_response_and_request_types(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "useProductions.ts").write_text(HOOK_FILE_CONTENT)

        results = parse_hooks(tmp_path)
        put_call = next(r for r in results if r.method == "put")
        assert put_call.response_type == "ProductionDetailResponse"
        assert put_call.request_type == "UpdateProductionRequest"

    def test_skips_client_ts(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        # client.ts should NOT be scanned even if it matches use*.ts accidentally
        (api_dir / "client.ts").write_text('apiClient.get<Foo>("/bar")')
        # But a normal hook file with "use" prefix should
        (api_dir / "useFoo.ts").write_text('const x = apiClient.get<Foo>("/bar")')

        results = parse_hooks(tmp_path)
        assert len(results) == 1
        assert results[0].file == "src/api/useFoo.ts"

    def test_empty_api_dir(self, tmp_path: Path) -> None:
        results = parse_hooks(tmp_path)
        assert results == []

    def test_extracts_query_params(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        content = """\
import { apiClient } from "./client";

export function useItems(state: string) {
  const params = new URLSearchParams();
  params.set("state", state);
  params.set("search", "foo");
  return apiClient.get<ItemList>("/items");
}
"""
        (api_dir / "useItems.ts").write_text(content)

        results = parse_hooks(tmp_path)
        assert len(results) == 1
        assert "state" in results[0].query_params
        assert "search" in results[0].query_params


# ---------------------------------------------------------------------------
# Tests: match_hooks_to_schema
# ---------------------------------------------------------------------------


class TestMatchHooksToSchema:
    def _make_schema(self) -> ParsedSchema:
        return parse_schema(MINIMAL_OPENAPI)

    def test_matched_pairs(self) -> None:
        schema = self._make_schema()
        hooks = [
            HookCall(file="f.ts", line=1, method="get", url="/productions", normalized_url="/productions"),
            HookCall(file="f.ts", line=2, method="get", url="/productions/${id}", normalized_url="/productions/{id}"),
        ]
        result = match_hooks_to_schema(hooks, schema)
        assert len(result.matched) == 2

    def test_orphan_endpoints(self) -> None:
        schema = self._make_schema()
        hooks = [
            HookCall(file="f.ts", line=1, method="get", url="/productions", normalized_url="/productions"),
        ]
        result = match_hooks_to_schema(hooks, schema)
        # /productions/{id} GET and /reports/summary GET are orphans
        orphan_paths = {op.path for op in result.orphan_endpoints}
        assert "/productions/{id}" in orphan_paths
        assert "/reports/summary" in orphan_paths

    def test_dead_endpoints(self) -> None:
        schema = self._make_schema()
        hooks = [
            HookCall(file="f.ts", line=1, method="get", url="/nonexistent", normalized_url="/nonexistent"),
        ]
        result = match_hooks_to_schema(hooks, schema)
        assert len(result.dead_endpoints) == 1
        assert result.dead_endpoints[0].normalized_url == "/nonexistent"

    def test_orphan_only_counts_get(self) -> None:
        """PUT operations without hooks should NOT appear as orphans."""
        schema = self._make_schema()
        hooks: list[HookCall] = []  # No hooks at all
        result = match_hooks_to_schema(hooks, schema)
        orphan_methods = {op.method for op in result.orphan_endpoints}
        assert orphan_methods == {"get"}

    def test_empty_inputs(self) -> None:
        schema = ParsedSchema()
        result = match_hooks_to_schema([], schema)
        assert result.matched == []
        assert result.orphan_endpoints == []
        assert result.dead_endpoints == []


# ---------------------------------------------------------------------------
# Tests: load_schema
# ---------------------------------------------------------------------------


class TestLoadSchema:
    def test_loads_cached_file(self, tmp_path: Path) -> None:
        schema_data = {"openapi": "3.0.0", "paths": {}}
        (tmp_path / "openapi.json").write_text(json.dumps(schema_data))

        result = load_schema(tmp_path, "mrp", offline=True)
        assert result == schema_data

    def test_returns_none_offline_no_cache(self, tmp_path: Path) -> None:
        result = load_schema(tmp_path, "mrp", offline=True)
        assert result is None

    def test_does_not_fetch_when_cached(self, tmp_path: Path) -> None:
        schema_data = {"openapi": "3.0.0", "paths": {"/test": {}}}
        (tmp_path / "openapi.json").write_text(json.dumps(schema_data))

        # Even with offline=False, should return cache without network call
        result = load_schema(tmp_path, "mrp", offline=False)
        assert result == schema_data


# ---------------------------------------------------------------------------
# Tests: Checkers
# ---------------------------------------------------------------------------


from kctl_react.core.compliance.api_check.checks import ALL_API_CHECKERS, CHECKER_MAP
from kctl_react.core.compliance.api_check.checks.endpoints import EndpointChecker
from kctl_react.core.compliance.api_check.checks.envelope import EnvelopeChecker
from kctl_react.core.compliance.api_check.checks.naming import NamingChecker
from kctl_react.core.compliance.api_check.checks.params import ParamChecker
from kctl_react.core.compliance.api_check.checks.requests import RequestChecker
from kctl_react.core.compliance.api_check.checks.types import TypeChecker


def _make_hook(
    *,
    file: str = "src/api/useProductions.ts",
    line: int = 1,
    method: str = "get",
    url: str = "/productions",
    normalized_url: str | None = None,
    response_type: str | None = "ProductionListResponse",
    request_type: str | None = None,
    query_params: list[str] | None = None,
) -> HookCall:
    return HookCall(
        file=file,
        line=line,
        method=method,
        url=url,
        normalized_url=normalized_url or url,
        response_type=response_type,
        request_type=request_type,
        query_params=query_params or [],
    )


def _make_operation(
    *,
    method: str = "get",
    path: str = "/productions",
    tag: str = "mrp-productions",
    response_schema: str | None = "ProductionListResponse",
    request_schema: str | None = None,
    parameters: list[str] | None = None,
) -> Operation:
    return Operation(
        method=method,
        path=path,
        tag=tag,
        response_schema=response_schema,
        request_schema=request_schema,
        parameters=parameters or [],
    )


class TestEndpointChecker:
    def test_orphan_endpoints(self) -> None:
        orphan_op = _make_operation(path="/reports/summary", tag="mrp-reports")
        match = MatchResult(matched=[], orphan_endpoints=[orphan_op], dead_endpoints=[])
        schema = ParsedSchema(operations=[orphan_op])

        result = EndpointChecker().check(schema, [], match)
        assert len(result.violations) == 1
        assert "Orphan endpoint" in result.violations[0].message
        assert "/reports/summary" in result.violations[0].message

    def test_dead_endpoints(self) -> None:
        dead_hook = _make_hook(method="get", url="/nonexistent", normalized_url="/nonexistent")
        match = MatchResult(matched=[], orphan_endpoints=[], dead_endpoints=[dead_hook])
        schema = ParsedSchema()

        result = EndpointChecker().check(schema, [dead_hook], match)
        assert len(result.violations) == 1
        assert "Dead endpoint" in result.violations[0].message
        assert "/nonexistent" in result.violations[0].message

    def test_no_violations(self) -> None:
        hook = _make_hook()
        op = _make_operation()
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = EndpointChecker().check(schema, [hook], match)
        assert len(result.violations) == 0
        assert result.score == 10


class TestTypeChecker:
    def test_missing_response_type(self) -> None:
        hook = _make_hook(response_type=None)
        op = _make_operation(response_schema="ProductionListResponse")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = TypeChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "Missing response type" in result.violations[0].message

    def test_type_mismatch(self) -> None:
        hook = _make_hook(response_type="WrongType")
        op = _make_operation(response_schema="ProductionListResponse")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = TypeChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "Type mismatch" in result.violations[0].message
        assert "WrongType" in result.violations[0].message

    def test_matching_types(self) -> None:
        hook = _make_hook(response_type="ProductionListResponse")
        op = _make_operation(response_schema="ProductionListResponse")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = TypeChecker().check(schema, [hook], match)
        assert len(result.violations) == 0


class TestRequestChecker:
    def test_missing_request_type(self) -> None:
        hook = _make_hook(method="put", request_type=None)
        op = _make_operation(method="put", request_schema="UpdateProductionRequest")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = RequestChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "Missing request body type" in result.violations[0].message

    def test_request_type_mismatch(self) -> None:
        hook = _make_hook(method="post", request_type="WrongRequest")
        op = _make_operation(method="post", request_schema="CreateProductionRequest")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = RequestChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "Request type mismatch" in result.violations[0].message

    def test_skips_get_requests(self) -> None:
        hook = _make_hook(method="get", request_type=None)
        op = _make_operation(method="get", request_schema="SomeRequest")
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = RequestChecker().check(schema, [hook], match)
        assert len(result.violations) == 0


class TestParamChecker:
    def test_unknown_query_param(self) -> None:
        hook = _make_hook(query_params=["state", "bogus"])
        op = _make_operation(parameters=["state", "search"])
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = ParamChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "'bogus'" in result.violations[0].message

    def test_valid_params(self) -> None:
        hook = _make_hook(query_params=["state"])
        op = _make_operation(parameters=["state", "search"])
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])
        schema = ParsedSchema(operations=[op])

        result = ParamChecker().check(schema, [hook], match)
        assert len(result.violations) == 0


class TestEnvelopeChecker:
    def test_conforming_schema(self) -> None:
        schema = ParsedSchema(
            response_schemas={
                "ProductionListResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {"type": "array"},
                    },
                }
            }
        )
        match = MatchResult()

        result = EnvelopeChecker().check(schema, [], match)
        assert len(result.violations) == 0

    def test_missing_success_key(self) -> None:
        schema = ParsedSchema(
            response_schemas={
                "BadResponse": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "array"},
                    },
                }
            }
        )
        match = MatchResult()

        result = EnvelopeChecker().check(schema, [], match)
        assert len(result.violations) == 1
        assert "missing success" in result.violations[0].message

    def test_missing_both_keys(self) -> None:
        schema = ParsedSchema(
            response_schemas={
                "EmptyResponse": {
                    "type": "object",
                    "properties": {},
                }
            }
        )
        match = MatchResult()

        result = EnvelopeChecker().check(schema, [], match)
        assert len(result.violations) == 2


class TestNamingChecker:
    def test_matching_tag(self) -> None:
        hook = _make_hook(file="src/api/useProductions.ts")
        op = _make_operation(tag="mrp-productions")
        schema = ParsedSchema(operations=[op])
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])

        result = NamingChecker().check(schema, [hook], match)
        assert len(result.violations) == 0

    def test_no_matching_tag(self) -> None:
        hook = _make_hook(file="src/api/useWidgets.ts")
        op = _make_operation(tag="mrp-productions")
        schema = ParsedSchema(operations=[op])
        match = MatchResult(matched=[(hook, op)], orphan_endpoints=[], dead_endpoints=[])

        result = NamingChecker().check(schema, [hook], match)
        assert len(result.violations) == 1
        assert "doesn't match any OpenAPI tag" in result.violations[0].message


class TestCheckerRegistry:
    def test_all_checkers_count(self) -> None:
        assert len(ALL_API_CHECKERS) == 6

    def test_checker_map_keys(self) -> None:
        expected = {"endpoints", "types", "requests", "params", "envelope", "naming"}
        assert set(CHECKER_MAP.keys()) == expected

    def test_checker_map_values(self) -> None:
        assert isinstance(CHECKER_MAP["endpoints"], EndpointChecker)
        assert isinstance(CHECKER_MAP["types"], TypeChecker)
        assert isinstance(CHECKER_MAP["requests"], RequestChecker)
        assert isinstance(CHECKER_MAP["params"], ParamChecker)
        assert isinstance(CHECKER_MAP["envelope"], EnvelopeChecker)
        assert isinstance(CHECKER_MAP["naming"], NamingChecker)


# ---------------------------------------------------------------------------
# CLI command tests (Typer CliRunner)
# ---------------------------------------------------------------------------

import json as _json

from typer.testing import CliRunner

from kctl_react.cli import app as cli_app

_runner = CliRunner()


def _add_openapi_to_app(mock_monorepo: Path, app_name: str) -> None:
    """Write a minimal openapi.json into an app directory."""
    app_dir = mock_monorepo / "apps" / app_name
    (app_dir / "openapi.json").write_text(_json.dumps(MINIMAL_OPENAPI, indent=2))

    # Also add a hooks file so there are matches
    api_dir = app_dir / "src" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "useProductions.ts").write_text(HOOK_FILE_CONTENT)


class TestApiCheckCLI:
    def test_api_check_single_app(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "api-check", "sfa"])
        assert result.exit_code == 0
        assert "Compliance Report: sfa" in result.output

    def test_api_check_all(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        _add_openapi_to_app(mock_monorepo, "mrp")
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "api-check", "--all", "--offline"]
        )
        assert result.exit_code == 0
        # Apps without openapi.json should produce warnings, not crash
        assert "No OpenAPI schema" in result.output or "Scorecard" in result.output

    def test_api_check_offline_no_schema(self, mock_monorepo: Path) -> None:
        """Offline mode with no cached schema should warn, not crash."""
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "api-check", "sfa", "--offline"])
        assert result.exit_code == 0
        assert "No OpenAPI schema" in result.output

    def test_api_check_json(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        result = _runner.invoke(cli_app, ["--json", "--root", str(mock_monorepo), "compliance", "api-check", "sfa"])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["app"] == "sfa"
        assert "categories" in data
        assert "grade" in data

    def test_api_check_categories_filter(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        result = _runner.invoke(
            cli_app,
            ["--json", "--root", str(mock_monorepo), "compliance", "api-check", "sfa", "--categories", "endpoints"],
        )
        assert result.exit_code == 0
        data = _json.loads(result.output)
        cat_names = [c["name"] for c in data["categories"]]
        assert cat_names == ["endpoints"]

    def test_api_check_min_score_pass(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "api-check", "sfa", "--min-score", "0"]
        )
        assert result.exit_code == 0

    def test_api_check_min_score_fail(self, mock_monorepo: Path) -> None:
        _add_openapi_to_app(mock_monorepo, "sfa")
        result = _runner.invoke(
            cli_app, ["--root", str(mock_monorepo), "compliance", "api-check", "sfa", "--min-score", "100"]
        )
        # With orphan endpoints + dead endpoints, score should be below 100%
        # (delete hook has no matching schema op)
        assert result.exit_code == 1

    def test_api_check_no_app_no_all(self, mock_monorepo: Path) -> None:
        result = _runner.invoke(cli_app, ["--root", str(mock_monorepo), "compliance", "api-check"])
        assert result.exit_code == 1
        assert "Specify an app name or use --all" in result.output
