"""Tests for `compose autodeploy` commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


def _projects_with_two_composes() -> list[dict]:
    return [
        {
            "projectId": "p-1",
            "name": "tpp",
            "compose": [],
            "environments": [
                {
                    "name": "production",
                    "compose": [
                        {"composeId": "c-1", "name": "tpp-odoo-erp", "composeStatus": "done"},
                        {"composeId": "c-2", "name": "tpp-infra-redis", "composeStatus": "done"},
                    ],
                }
            ],
        },
    ]


class TestStatus:
    def test_status_table(self, mock_client: MagicMock) -> None:
        # /project.all → two composes. /compose.one → one with autoDeploy=true, one false
        def fake_get(path: str, params: dict | None = None):
            if path == "/project.all":
                return _projects_with_two_composes()
            if path == "/compose.one":
                cid = (params or {}).get("composeId")
                return {"composeId": cid, "autoDeploy": cid == "c-1"}
            return []

        mock_client.get.side_effect = fake_get
        result = runner.invoke(app, ["--json", "compose", "autodeploy", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        c1 = next(r for r in data if r["composeId"] == "c-1")
        c2 = next(r for r in data if r["composeId"] == "c-2")
        assert c1["autoDeploy"] is True
        assert c2["autoDeploy"] is False

    def test_only_enabled_filter(self, mock_client: MagicMock) -> None:
        def fake_get(path: str, params: dict | None = None):
            if path == "/project.all":
                return _projects_with_two_composes()
            if path == "/compose.one":
                cid = (params or {}).get("composeId")
                return {"composeId": cid, "autoDeploy": cid == "c-1"}
            return []

        mock_client.get.side_effect = fake_get
        result = runner.invoke(app, ["--json", "compose", "autodeploy", "status", "--only-enabled"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1 and data[0]["composeId"] == "c-1"


class TestToggle:
    def test_disable_calls_update_with_false(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        mock_client.get.return_value = {"composeId": "c-1", "autoDeploy": False}
        result = runner.invoke(app, ["compose", "autodeploy", "disable", "c-1"])
        assert result.exit_code == 0
        assert mock_client.post.called
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"] == {"composeId": "c-1", "autoDeploy": False}

    def test_enable_calls_update_with_true(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        mock_client.get.return_value = {"composeId": "c-1", "autoDeploy": True}
        result = runner.invoke(app, ["compose", "autodeploy", "enable", "c-1"])
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"] == {"composeId": "c-1", "autoDeploy": True}

    def test_disable_exits_nonzero_if_verification_fails(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        # Verification still reports true after disable — stuck
        mock_client.get.return_value = {"composeId": "c-1", "autoDeploy": True}
        result = runner.invoke(app, ["compose", "autodeploy", "disable", "c-1"])
        assert result.exit_code == 1


class TestDisableAll:
    def test_disable_all_dry_run(self, mock_client: MagicMock) -> None:
        def fake_get(path: str, params: dict | None = None):
            if path == "/project.all":
                return _projects_with_two_composes()
            if path == "/compose.one":
                cid = (params or {}).get("composeId")
                return {"composeId": cid, "autoDeploy": cid == "c-1"}
            return []

        mock_client.get.side_effect = fake_get
        result = runner.invoke(app, ["compose", "autodeploy", "disable-all", "--dry-run"])
        assert result.exit_code == 0
        # Dry-run should not POST
        assert not mock_client.post.called

    def test_disable_all_force(self, mock_client: MagicMock) -> None:
        call_state = {"disabled": False}

        def fake_get(path: str, params: dict | None = None):
            if path == "/project.all":
                return _projects_with_two_composes()
            if path == "/compose.one":
                cid = (params or {}).get("composeId")
                # c-1 starts true; flips to false once disable is called
                if cid == "c-1":
                    return {"composeId": cid, "autoDeploy": not call_state["disabled"]}
                return {"composeId": cid, "autoDeploy": False}
            return []

        def fake_post(path: str, json: dict | None = None):
            if json and json.get("composeId") == "c-1" and json.get("autoDeploy") is False:
                call_state["disabled"] = True
            return {}

        mock_client.get.side_effect = fake_get
        mock_client.post.side_effect = fake_post
        result = runner.invoke(app, ["compose", "autodeploy", "disable-all", "--force"])
        assert result.exit_code == 0
        assert call_state["disabled"]
