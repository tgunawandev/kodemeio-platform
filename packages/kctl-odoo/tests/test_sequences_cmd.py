"""Tests for sequences command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client=None):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestSequencesImport:
    def test_import(self):
        from kctl_odoo.commands.sequences_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.sequences_cmd import get, list_sequences, preview, reset

        assert callable(list_sequences)
        assert callable(get)
        assert callable(reset)
        assert callable(preview)


class TestSequencesList:
    def test_list_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import list_sequences

        ctx = _make_ctx(actx)
        list_sequences(ctx, model=None, limit=50)

    def test_list_with_data(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Sale Order",
                "code": "sale.order",
                "prefix": "S",
                "suffix": "",
                "number_next": 100,
                "padding": 5,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import list_sequences

        ctx = _make_ctx(actx)
        list_sequences(ctx, model=None, limit=50)

    def test_list_with_model_filter(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import list_sequences

        ctx = _make_ctx(actx)
        list_sequences(ctx, model="sale", limit=50)
        # Check domain was passed with ilike filter
        call_args = c.search_read.call_args
        assert call_args is not None
        kwargs = call_args.kwargs if call_args.kwargs else {}
        domain = kwargs.get("domain", call_args.args[1] if len(call_args.args) > 1 else [])
        assert any("ilike" in str(d) for d in domain)


class TestSequencesGet:
    def test_get_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import get

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            get(ctx, code="nonexistent.code")

    def test_get_found(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Sale Order",
                "code": "sale.order",
                "prefix": "S",
                "suffix": "",
                "number_next": 100,
                "number_increment": 1,
                "padding": 5,
                "active": True,
                "company_id": [1, "My Company"],
                "implementation": "standard",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import get

        ctx = _make_ctx(actx)
        get(ctx, code="sale.order")


class TestSequencesReset:
    def test_reset_requires_force(self):
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import reset

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            reset(ctx, code="sale.order", number=1000, force=False)

    def test_reset_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import reset

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            reset(ctx, code="nonexistent.code", number=1000, force=True)

    def test_reset_success(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "name": "Sale Order", "code": "sale.order", "number_next": 500}]
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import reset

        ctx = _make_ctx(actx)
        reset(ctx, code="sale.order", number=1000, force=True)
        c.execute_kw.assert_called_once_with("ir.sequence", "write", [[1], {"number_next_actual": 1000}])


class TestSequencesPreview:
    def test_preview(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Sale Order",
                "code": "sale.order",
                "prefix": "S",
                "suffix": "",
                "number_next": 100,
                "padding": 5,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import preview

        ctx = _make_ctx(actx)
        preview(ctx, code="sale.order", count=3)

    def test_preview_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.sequences_cmd import preview

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            preview(ctx, code="nonexistent.code", count=3)

    def test_preview_generates_correct_format(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Sale Order",
                "code": "sale.order",
                "prefix": "S",
                "suffix": "/2026",
                "number_next": 100,
                "padding": 5,
            }
        ]
        actx = _make_actx(client=c)
        # Use JSON mode to capture output
        actx.json_mode = True
        captured = {}

        def capture_json(data):
            captured.update(data)

        actx.output.raw_json = capture_json
        from kctl_odoo.commands.sequences_cmd import preview

        ctx = _make_ctx(actx)
        preview(ctx, code="sale.order", count=3)
        assert "previews" in captured
        assert len(captured["previews"]) == 3
        assert captured["previews"][0] == "S00100/2026"
        assert captured["previews"][1] == "S00101/2026"
        assert captured["previews"][2] == "S00102/2026"
