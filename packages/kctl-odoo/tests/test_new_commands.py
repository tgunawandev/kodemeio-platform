"""Tests for new commands: modules check, fastapi, dev-mode, config quick."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click
import pytest

from kctl_odoo.core.output import Output


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    actx.profile = None
    actx.url_override = None
    actx.api_key_override = None
    actx.database_override = None
    actx.username_override = None
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# modules check
# ---------------------------------------------------------------------------


class TestModulesCheck:
    def test_check_installed(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.search_read.return_value = [
            {"name": "sale", "state": "installed", "installed_version": "18.0.1.0", "shortdesc": "Sales"}
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import check

        check(ctx, name="sale")

        data = json.loads(capsys.readouterr().out)
        assert data["installed"] is True
        assert data["state"] == "installed"

    def test_check_not_installed(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.search_read.return_value = [
            {"name": "sale", "state": "uninstalled", "installed_version": "", "shortdesc": "Sales"}
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import check

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            check(ctx, name="sale")

        data = json.loads(capsys.readouterr().out)
        assert data["installed"] is False

    def test_check_not_found(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.search_read.return_value = []
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.modules import check

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            check(ctx, name="nonexistent")

        data = json.loads(capsys.readouterr().out)
        assert data["found"] is False


# ---------------------------------------------------------------------------
# dev-mode
# ---------------------------------------------------------------------------


class TestDevMode:
    def test_status_all(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.search_read.return_value = []  # no params set
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.dev_mode import status

        status(ctx, app_name=None)

        data = json.loads(capsys.readouterr().out)
        from kctl_odoo.core.utils import KNOWN_APPS

        assert isinstance(data, list)
        assert len(data) == len(KNOWN_APPS)
        assert all(d["dev_mode"] is None for d in data)

    def test_status_single(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.search_read.return_value = [{"value": "True"}]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.dev_mode import status

        status(ctx, app_name="tpm")

        data = json.loads(capsys.readouterr().out)
        assert data["app"] == "tpm"
        assert data["dev_mode"] is True

    def test_enable(self, mock_client: MagicMock) -> None:
        mock_client.search_read.return_value = [{"value": "True"}]
        actx = _make_actx(json_mode=False, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.dev_mode import enable

        enable(ctx, app_name="sfa")

        mock_client.execute_kw.assert_called_once_with(
            "ir.config_parameter",
            "set_param",
            ["sfa.dev_mode", "True"],
        )


# ---------------------------------------------------------------------------
# fastapi health
# ---------------------------------------------------------------------------


class TestFastapiHealth:
    @patch("kctl_odoo.core.config.resolve_connection")
    @patch("httpx.Client")
    def test_health_ok(
        self, mock_httpx_cls: MagicMock, mock_resolve: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_resolve.return_value = ("http://localhost:8069", "odoo_tpm", "admin", "admin")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"paths": {"/auth/login": {"post": {"summary": "Login"}}}}
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.fastapi_cmd import health

        health(ctx, app_name="tpm")

        data = json.loads(capsys.readouterr().out)
        assert data["healthy"] is True
        assert data["app"] == "tpm"
        assert data["endpoints"] >= 1


# ---------------------------------------------------------------------------
# fastapi endpoints
# ---------------------------------------------------------------------------


class TestFastapiEndpoints:
    @patch("kctl_odoo.core.config.resolve_connection")
    @patch("httpx.Client")
    def test_endpoints_json(
        self, mock_httpx_cls: MagicMock, mock_resolve: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_resolve.return_value = ("http://localhost:8069", "odoo_tpm", "admin", "admin")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "paths": {
                "/auth/login": {"post": {"summary": "Login"}},
                "/promotions": {"get": {"summary": "List promotions"}},
            }
        }
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        actx = _make_actx(json_mode=True)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.fastapi_cmd import endpoints

        endpoints(ctx, app_name="tpm")

        data = json.loads(capsys.readouterr().out)
        assert data["total"] == 2
        assert data["app"] == "tpm"
