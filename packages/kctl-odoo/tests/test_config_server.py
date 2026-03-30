"""Tests for the config-server command group (params-list/get/set, mail-outgoing, defaults-list)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import click
import pytest

from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.output import Output

# Typer raises click.exceptions.Exit (not SystemExit) for raise typer.Exit(code).
# SystemExit uses .code; click.exceptions.Exit uses .exit_code.
_EXIT = (SystemExit, click.exceptions.Exit)


def _exit_code(exc_info: pytest.ExceptionInfo) -> int:
    """Return the integer exit code from a caught SystemExit or click.exceptions.Exit."""
    exc = exc_info.value
    if isinstance(exc, SystemExit):
        return int(exc.code)
    return int(exc.exit_code)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_diagnose.py / test_new_commands.py)
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    actx.profile = "test"
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# params-list
# ---------------------------------------------------------------------------


class TestParamsList:
    def test_returns_table_with_params(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """params-list returns a JSON array of system parameters in JSON mode."""
        mock_client.search_read.return_value = [
            {"id": 1, "key": "web.base.url", "value": "https://odoo.example.com"},
            {"id": 2, "key": "database.uuid", "value": "abc-123"},
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_list

        params_list(ctx, search=None, limit=100)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["key"] == "web.base.url"

    def test_search_filter_passed_to_client(self, mock_client: MagicMock) -> None:
        """params-list with --search appends an ilike domain filter."""
        mock_client.search_read.return_value = []
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_list

        params_list(ctx, search="mail", limit=50)

        call_kwargs = mock_client.search_read.call_args
        domain = call_kwargs[1]["domain"] if call_kwargs[1] else call_kwargs[0][1]
        assert ("key", "ilike", "mail") in domain

    def test_empty_result_does_not_crash(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """params-list with zero results renders an empty table without error."""
        mock_client.search_read.return_value = []
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_list

        params_list(ctx, search=None, limit=100)

        data = json.loads(capsys.readouterr().out)
        assert data == []


# ---------------------------------------------------------------------------
# params-get
# ---------------------------------------------------------------------------


class TestParamsGet:
    def test_found_outputs_detail(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """params-get prints param detail in JSON mode when the key exists."""
        mock_client.search_read.return_value = [{"id": 5, "key": "web.base.url", "value": "https://odoo.example.com"}]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_get

        params_get(ctx, key="web.base.url")

        data = json.loads(capsys.readouterr().out)
        assert data["key"] == "web.base.url"
        assert data["value"] == "https://odoo.example.com"

    def test_not_found_exits_nonzero(self, mock_client: MagicMock) -> None:
        """params-get raises Exit(1) when the key does not exist."""
        mock_client.search_read.return_value = []
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_get

        with pytest.raises(_EXIT) as exc_info:
            params_get(ctx, key="nonexistent.key")

        assert _exit_code(exc_info) == 1


# ---------------------------------------------------------------------------
# params-set
# ---------------------------------------------------------------------------


class TestParamsSet:
    def test_calls_set_param(self, mock_client: MagicMock) -> None:
        """params-set calls execute_kw with set_param RPC."""
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import params_set

        params_set(ctx, key="web.base.url", value="https://new.example.com")

        mock_client.execute_kw.assert_called_once_with(
            "ir.config_parameter", "set_param", ["web.base.url", "https://new.example.com"]
        )


# ---------------------------------------------------------------------------
# mail-outgoing
# ---------------------------------------------------------------------------


class TestMailOutgoing:
    def test_lists_servers_in_json_mode(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """mail-outgoing lists SMTP servers as JSON array."""
        mock_client.search_read.return_value = [
            {
                "id": 1,
                "name": "Main SMTP",
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_encryption": "starttls",
                "smtp_user": "user@example.com",
                "active": True,
                "sequence": 10,
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_outgoing

        mail_outgoing(ctx)

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Main SMTP"
        assert data[0]["smtp_host"] == "smtp.example.com"

    def test_empty_returns_empty_json(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """mail-outgoing returns [] in JSON mode when no servers are configured."""
        mock_client.search_read.return_value = []
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_outgoing

        mail_outgoing(ctx)

        data = json.loads(capsys.readouterr().out)
        assert data == []


# ---------------------------------------------------------------------------
# mail-outgoing-add
# ---------------------------------------------------------------------------


class TestMailOutgoingAdd:
    def test_creates_server_and_reports_id(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """mail-outgoing-add creates a server and outputs its ID in JSON mode."""
        mock_client.create.return_value = 42
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_outgoing_add

        mail_outgoing_add(
            ctx,
            name="New SMTP",
            host="smtp.example.com",
            port=587,
            user="user@example.com",
            password="secret",
            encryption="starttls",
        )

        data = json.loads(capsys.readouterr().out)
        assert data["id"] == 42
        assert data["name"] == "New SMTP"

    def test_invalid_encryption_exits_nonzero(self, mock_client: MagicMock) -> None:
        """mail-outgoing-add exits 1 when an unsupported encryption value is given."""
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_outgoing_add

        with pytest.raises(_EXIT) as exc_info:
            mail_outgoing_add(
                ctx,
                name="Bad",
                host="smtp.example.com",
                port=25,
                user=None,
                password=None,
                encryption="tls",  # invalid
            )

        assert _exit_code(exc_info) == 1

    def test_rpc_error_exits_nonzero(self, mock_client: MagicMock) -> None:
        """mail-outgoing-add exits 1 when Odoo returns an RPCError."""
        mock_client.create.side_effect = RPCError({"message": "Constraint violated"})
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_outgoing_add

        with pytest.raises(_EXIT) as exc_info:
            mail_outgoing_add(
                ctx,
                name="SMTP",
                host="smtp.example.com",
                port=25,
                user=None,
                password=None,
                encryption="none",
            )

        assert _exit_code(exc_info) == 1


# ---------------------------------------------------------------------------
# mail-incoming
# ---------------------------------------------------------------------------


class TestMailIncoming:
    def test_fetchmail_not_installed_warns(self, mock_client: MagicMock) -> None:
        """mail-incoming shows a warning (not error) when fetchmail is not installed."""
        mock_client.search_read.side_effect = RPCError({"message": "fetchmail.server does not exist"})
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_incoming

        # Should not raise — fetchmail absence is a known optional condition
        mail_incoming(ctx)

    def test_fetchmail_not_installed_empty_json(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """mail-incoming returns [] in JSON mode when fetchmail is absent."""
        mock_client.search_read.side_effect = RPCError({"message": "fetchmail.server does not exist"})
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import mail_incoming

        mail_incoming(ctx)

        data = json.loads(capsys.readouterr().out)
        assert data == []


# ---------------------------------------------------------------------------
# defaults-list
# ---------------------------------------------------------------------------


class TestDefaultsList:
    def test_lists_defaults_in_json_mode(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """defaults-list returns JSON array of ir.default records."""
        mock_client.search_read.return_value = [
            {
                "id": 1,
                "field_id": [10, "sale.order / pricelist_id"],
                "json_value": "1",
                "company_id": [1, "My Company"],
                "user_id": False,
            }
        ]
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import defaults_list

        defaults_list(ctx, model=None)

        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["id"] == 1

    def test_model_filter_queries_field_ids(self, mock_client: MagicMock) -> None:
        """defaults-list with --model first searches ir.model.fields for that model."""
        mock_client.search.return_value = [5, 6]
        mock_client.search_read.return_value = []
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import defaults_list

        defaults_list(ctx, model="res.partner")

        # search on ir.model.fields should have been called with the model domain
        mock_client.search.assert_called_once_with("ir.model.fields", [("model", "=", "res.partner")])


# ---------------------------------------------------------------------------
# sync-base-url
# ---------------------------------------------------------------------------


class TestSyncBaseUrl:
    def test_sync_updates_web_base_url(self, mock_client: MagicMock) -> None:
        """sync-base-url should call set_param with the profile URL."""
        mock_client._base_url = "http://localhost:8069"
        mock_client.search_read.return_value = [{"id": 1, "key": "web.base.url", "value": "http://localhost:8869"}]
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import sync_base_url

        sync_base_url(ctx, all_dbs=False)

        mock_client.execute_kw.assert_called_once_with(
            "ir.config_parameter", "set_param", ["web.base.url", "http://localhost:8069"]
        )

    def test_sync_skips_when_already_correct(self, mock_client: MagicMock) -> None:
        """sync-base-url should skip if web.base.url already matches."""
        mock_client._base_url = "http://localhost:8069"
        mock_client.search_read.return_value = [{"id": 1, "key": "web.base.url", "value": "http://localhost:8069"}]
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        from kctl_odoo.commands.config_server import sync_base_url

        sync_base_url(ctx, all_dbs=False)

        mock_client.execute_kw.assert_not_called()
