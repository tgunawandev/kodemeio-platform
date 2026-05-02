"""Tests for the pricelist command group."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from kctl_lib import Output

from kctl_odoo.core.callbacks import AppContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_actx(client=None, json_mode=False):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = json_mode
    actx.client = client or MagicMock()
    actx.output = Output(json_mode=json_mode, quiet=True)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


class TestPricelistImport:
    def test_module_imports(self):
        from kctl_odoo.commands import pricelist_cmd

        assert pricelist_cmd.app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.pricelist_cmd import (
            analyze,
            export_template,
            items,
            strata,
        )

        assert callable(items)
        assert callable(strata)
        assert callable(analyze)
        assert callable(export_template)

    def test_registered_in_cli(self):
        from kctl_odoo.cli import app

        names = {ti.name for ti in app.registered_groups}
        assert "pricelist" in names


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------


class TestItems:
    def test_no_items(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 39752, "name": "TLN-JKT_JAKARTA", "currency_id": [1, "IDR"]}],  # _resolve_pricelist
            [],  # actual items query
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import items

        items(_make_ctx(actx), pricelist="TLN-JKT_JAKARTA", product=None, active_only=False, limit=200)

    def test_items_renders(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 39752, "name": "TLN-JKT_JAKARTA", "currency_id": [1, "IDR"]}],  # pricelist resolve
            [
                {
                    "id": 1,
                    "product_tmpl_id": [550, "[01010101160] ECO TEA CUP 24"],
                    "applied_on": "1_product",
                    "min_quantity": 24.0,
                    "compute_price": "percentage",
                    "fixed_price": 0.0,
                    "percent_price": 5.5,
                    "date_start": "2026-01-01 00:00:00",
                    "date_end": False,
                },
            ],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import items

        items(_make_ctx(actx), pricelist="TLN-JKT_JAKARTA", product=None, active_only=False, limit=200)

    def test_items_with_product_filter(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 39752, "name": "TLN-JKT_JAKARTA", "currency_id": [1, "IDR"]}],  # pricelist
            [{"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}],  # product
            [],  # items
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import items

        items(_make_ctx(actx), pricelist="TLN-JKT_JAKARTA", product="ECO TEA", active_only=False, limit=200)

    def test_items_pricelist_not_found(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import items

        with pytest.raises(typer.BadParameter):
            items(_make_ctx(actx), pricelist="NOPE", product=None, active_only=False, limit=200)

    def test_items_resolves_by_id(self):
        c = MagicMock()
        c.read.return_value = [{"id": 39752, "name": "TLN-JKT_JAKARTA", "currency_id": [1, "IDR"]}]
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import items

        items(_make_ctx(actx), pricelist="39752", product=None, active_only=False, limit=200)
        c.read.assert_called_once()


# ---------------------------------------------------------------------------
# strata
# ---------------------------------------------------------------------------


class TestStrata:
    def test_strata_empty(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}],
            [],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import strata

        strata(_make_ctx(actx), product="ECO TEA", prefix="TLN-", latest_only=False)

    def test_strata_renders(self):
        c = MagicMock()
        c.search_read.side_effect = [
            [{"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}],
            [
                {
                    "id": 1,
                    "pricelist_id": [39752, "TLN-JKT_JAKARTA (IDR)"],
                    "min_quantity": 24.0,
                    "compute_price": "percentage",
                    "percent_price": 5.5,
                    "fixed_price": 0.0,
                    "date_start": "2026-01-01 00:00:00",
                    "date_end": False,
                },
                {
                    "id": 2,
                    "pricelist_id": [39752, "TLN-JKT_JAKARTA (IDR)"],
                    "min_quantity": 1800.0,
                    "compute_price": "percentage",
                    "percent_price": 8.0,
                    "fixed_price": 0.0,
                    "date_start": "2026-01-01 00:00:00",
                    "date_end": False,
                },
            ],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import strata

        strata(_make_ctx(actx), product="ECO TEA", prefix="TLN-", latest_only=False)

    def test_strata_latest_only_filters(self):
        c = MagicMock()
        # Identifier "550" is a digit → resolver hits c.read, not c.search_read
        c.read.return_value = [
            {"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}
        ]
        c.search_read.return_value = [
            # Old cohort (filtered out)
            {
                "id": 1,
                "pricelist_id": [39752, "TLN-JKT"],
                "min_quantity": 24.0,
                "compute_price": "percentage",
                "percent_price": 2.0,
                "fixed_price": 0.0,
                "date_start": "2022-01-01 07:00:00",
                "date_end": False,
            },
            # New cohort (kept)
            {
                "id": 2,
                "pricelist_id": [39752, "TLN-JKT"],
                "min_quantity": 24.0,
                "compute_price": "percentage",
                "percent_price": 5.0,
                "fixed_price": 0.0,
                "date_start": "2026-01-01 07:00:00",
                "date_end": False,
            },
        ]
        actx = _make_actx(client=c, json_mode=True)
        captured = {}
        actx.output.raw_json = lambda data: captured.setdefault("data", data)
        from kctl_odoo.commands.pricelist_cmd import strata

        strata(_make_ctx(actx), product="550", prefix=None, latest_only=True)
        assert len(captured["data"]) == 1
        assert captured["data"][0]["id"] == 2


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_analyze_groups_identical_strata(self):
        c = MagicMock()
        # Identifier "550" → c.read for product resolve
        c.read.return_value = [
            {"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}
        ]
        c.search_read.return_value = [
            # PL 1 — pattern A
            {
                "pricelist_id": [1, "TLN-A"],
                "min_quantity": 24.0,
                "compute_price": "percentage",
                "percent_price": 5.0,
                "fixed_price": 0.0,
                "date_start": "2026-01-01 00:00:00",
            },
            # PL 2 — same pattern A
            {
                "pricelist_id": [2, "TLN-B"],
                "min_quantity": 24.0,
                "compute_price": "percentage",
                "percent_price": 5.0,
                "fixed_price": 0.0,
                "date_start": "2026-01-01 00:00:00",
            },
            # PL 3 — different pattern B
            {
                "pricelist_id": [3, "TLN-C"],
                "min_quantity": 24.0,
                "compute_price": "percentage",
                "percent_price": 8.0,
                "fixed_price": 0.0,
                "date_start": "2026-01-01 00:00:00",
            },
        ]
        actx = _make_actx(client=c, json_mode=True)
        captured = {}
        actx.output.raw_json = lambda data: captured.setdefault("data", data)
        from kctl_odoo.commands.pricelist_cmd import analyze

        analyze(_make_ctx(actx), product="550", prefix="TLN-", latest_only=True)
        # 2 distinct fingerprints
        assert len(captured["data"]) == 2
        # First bucket (most pricelists) is pattern A with 2 PLs
        assert len(captured["data"][0]["pricelists"]) == 2

    def test_analyze_empty(self):
        c = MagicMock()
        c.read.return_value = [
            {"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}
        ]
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import analyze

        analyze(_make_ctx(actx), product="550", prefix="TLN-", latest_only=True)


# ---------------------------------------------------------------------------
# export-template
# ---------------------------------------------------------------------------


class TestExportTemplate:
    def test_export_template_writes_csv(self, tmp_path: Path):
        c = MagicMock()
        # Identifiers "550" + "554" both digit → both go through c.read
        prod_records = {
            550: {"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92},
            554: {"id": 554, "default_code": "01020101180", "name": "GRESSTEA CUP 24", "list_price": 668.93},
        }
        c.read.side_effect = lambda model, ids, fields: [prod_records[i] for i in ids]
        c.search_read.return_value = [
            {"id": 39752, "name": "TLN-JKT_JAKARTA"},
            {"id": 39749, "name": "TLN-BJR_BANDUNG"},
        ]
        actx = _make_actx(client=c)
        out_file = tmp_path / "tln-template.csv"
        from kctl_odoo.commands.pricelist_cmd import export_template

        export_template(
            _make_ctx(actx),
            mode="add-lines",
            prefix="TLN-",
            products="550,554",
            output=out_file,
        )
        assert out_file.exists()
        lines = out_file.read_text().splitlines()
        # Header + 2 pricelists × 2 products = 5 lines
        assert len(lines) == 5
        # Header has the safe ID columns
        assert "pricelist_id/.id" in lines[0]
        assert "product_tmpl_id/.id" in lines[0]
        # First data row points at pricelist 39752 + product 550
        assert lines[1].startswith("39752,TLN-JKT_JAKARTA,1_product,550,")
        # compute_price is locked to percentage
        assert ",percentage," in lines[1]

    def test_export_template_rejects_unknown_mode(self):
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import export_template

        with pytest.raises(typer.Exit) as ei:
            export_template(_make_ctx(actx), mode="update-prices", prefix=None, products="550", output=None)
        assert ei.value.exit_code == 2

    def test_export_template_requires_products(self):
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import export_template

        with pytest.raises(typer.Exit) as ei:
            export_template(_make_ctx(actx), mode="add-lines", prefix="TLN-", products=None, output=None)
        assert ei.value.exit_code == 2

    def test_export_template_no_pricelists_found(self, tmp_path: Path):
        c = MagicMock()
        c.read.return_value = [
            {"id": 550, "default_code": "01010101160", "name": "ECO TEA CUP 24", "list_price": 715.92}
        ]
        c.search_read.return_value = []  # no pricelists matching prefix
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pricelist_cmd import export_template

        with pytest.raises(typer.Exit) as ei:
            export_template(
                _make_ctx(actx),
                mode="add-lines",
                prefix="NOPE-",
                products="550",
                output=tmp_path / "x.csv",
            )
        assert ei.value.exit_code == 1


# ---------------------------------------------------------------------------
# master-data pricelists --prefix
# ---------------------------------------------------------------------------


class TestMasterDataPrefixFlag:
    def test_pricelists_with_prefix_filters_domain(self):
        c = MagicMock()
        c.search_read.return_value = [
            {"id": 39752, "name": "TLN-JKT_JAKARTA", "currency_id": [1, "IDR"]},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.configure import pricelists

        pricelists(_make_ctx(actx), prefix="TLN-", limit=50)
        # Verify the domain was passed
        kwargs = c.search_read.call_args.kwargs
        args = c.search_read.call_args.args
        domain = kwargs.get("domain") or (args[1] if len(args) > 1 else [])
        assert any("=like" in str(t) for t in domain), f"domain missing =like: {domain}"

    def test_pricelists_without_prefix_no_filter(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.configure import pricelists

        pricelists(_make_ctx(actx), prefix=None, limit=50)
