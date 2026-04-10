"""Tests for staging neutralize-staging command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None, database: str = "stg_mac_odoo_erp") -> MagicMock:
    from kctl_lib import Output

    c = client or MagicMock()
    c.database = database
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = c
    actx.output = Output(json_mode=False, quiet=True)
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


def _configure_client_defaults(c: MagicMock) -> None:
    """Default: no mail servers, no payment providers, no companies to prefix."""

    def search(model: str, domain=None, **kwargs):
        return []

    def search_read(model: str, domain=None, fields=None, **kwargs):
        return []

    def execute_kw(model: str, method: str, args=None, kwargs=None):
        # Default: model exists (webhook check) returns True
        if method == "check_object_reference":
            return [1, 1]
        return []

    c.search.side_effect = search
    c.search_read.side_effect = search_read
    c.execute_kw.side_effect = execute_kw
    c.write.return_value = True


class TestStagingImport:
    def test_import(self) -> None:
        from kctl_odoo.commands.staging_cmd import app

        assert app is not None

    def test_command_callable(self) -> None:
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        assert callable(neutralize_staging)


class TestSafetyGuard:
    def test_refuses_production_database(self) -> None:
        """Must refuse if database name lacks 'stg' or 'staging'."""
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)
        actx = _make_actx(client=c, database="mac_odoo_erp")
        ctx = _make_ctx(actx)

        with pytest.raises(typer.Exit):
            neutralize_staging(ctx, admin_password="secret", company_prefix="[STG] ", dry_run=False)

        # Must NOT have written anything
        c.write.assert_not_called()

    def test_allows_stg_prefix(self) -> None:
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)
        actx = _make_actx(client=c, database="stg_mac_odoo_erp")
        ctx = _make_ctx(actx)

        # Should not raise
        neutralize_staging(ctx, admin_password="secret", company_prefix="[STG] ", dry_run=False)

    def test_allows_staging_name(self) -> None:
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)
        actx = _make_actx(client=c, database="staging_anything")
        ctx = _make_ctx(actx)

        neutralize_staging(ctx, admin_password="secret", company_prefix="[STG] ", dry_run=False)


class TestNeutralizeBehaviour:
    def test_neutralize_disables_mail_servers(self) -> None:
        """Given active mail server ids, write([ids], {active: False}) is called."""
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)

        def search(model, domain=None, **kwargs):
            if model == "ir.mail_server":
                return [1, 2, 3]
            return []

        c.search.side_effect = search
        actx = _make_actx(client=c, database="stg_mac_odoo_erp")
        ctx = _make_ctx(actx)

        neutralize_staging(ctx, admin_password="secret", company_prefix="[STG] ", dry_run=False)

        # Verify write was called to deactivate mail servers
        mail_write_calls = [call for call in c.write.call_args_list if call.args and call.args[0] == "ir.mail_server"]
        assert len(mail_write_calls) == 1
        assert mail_write_calls[0].args[1] == [1, 2, 3]
        assert mail_write_calls[0].args[2] == {"active": False}

    def test_neutralize_dry_run_does_not_write(self) -> None:
        """Dry run performs no write calls."""
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)

        def search(model, domain=None, **kwargs):
            if model == "ir.mail_server":
                return [1, 2]
            if model == "payment.provider":
                return [10]
            if model == "webhook.endpoint":
                return [20]
            if model == "res.company":
                return [1]
            return []

        def search_read(model, domain=None, fields=None, **kwargs):
            if model == "res.company":
                return [{"id": 1, "name": "Acme"}]
            if model == "res.users":
                return [{"id": 2, "login": "admin"}]
            return []

        c.search.side_effect = search
        c.search_read.side_effect = search_read
        actx = _make_actx(client=c, database="stg_mac_odoo_erp")
        ctx = _make_ctx(actx)

        neutralize_staging(ctx, admin_password="secret", company_prefix="[STG] ", dry_run=True)

        c.write.assert_not_called()

    def test_neutralize_is_idempotent(self) -> None:
        """Second run on already-neutralized instance results in zero writes."""
        from kctl_odoo.commands.staging_cmd import neutralize_staging

        c = MagicMock()
        _configure_client_defaults(c)

        # Already neutralized: no active mail servers, no enabled providers,
        # no active webhooks, company already prefixed, web.base.url already matches.
        def search(model, domain=None, **kwargs):
            return []

        def search_read(model, domain=None, fields=None, **kwargs):
            if model == "res.company":
                return [{"id": 1, "name": "[STG] Acme"}]
            if model == "ir.config_parameter":
                # web.base.url already set to current
                return [{"id": 99, "key": "web.base.url", "value": "https://stg.example.com"}]
            if model == "res.users":
                return [{"id": 2, "login": "admin"}]
            return []

        c.search.side_effect = search
        c.search_read.side_effect = search_read
        # Provide a base_url so the web.base.url check can compare
        c._base_url = "https://stg.example.com"
        actx = _make_actx(client=c, database="stg_mac_odoo_erp")
        ctx = _make_ctx(actx)

        neutralize_staging(
            ctx,
            admin_password=None,  # no password change -> skip
            company_prefix="[STG] ",
            dry_run=False,
        )

        # No writes on any disable-target models
        written_models = [call.args[0] for call in c.write.call_args_list if call.args]
        assert "ir.mail_server" not in written_models
        assert "payment.provider" not in written_models
        assert "webhook.endpoint" not in written_models
        assert "res.company" not in written_models
