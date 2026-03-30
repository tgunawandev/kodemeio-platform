"""Tests for field_helpers module."""

from __future__ import annotations
from unittest.mock import MagicMock

from kctl_odoo.core.field_helpers import safe_fields, get_model_fields, classify_fields


class TestSafeFields:
    def test_returns_existing_fields(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "name": {"type": "char", "string": "Name"},
            "code": {"type": "char", "string": "Code"},
            "active": {"type": "boolean", "string": "Active"},
            "display_name": {"type": "char", "string": "Display Name"},
            "create_date": {"type": "datetime", "string": "Created"},
        }
        result = safe_fields(c, "form.type", ["name", "model_id", "active", "code"])
        assert result == ["name", "active", "code"]
        assert "model_id" not in result

    def test_fallback_on_error(self):
        c = MagicMock()
        c.execute_kw.side_effect = Exception("connection error")
        result = safe_fields(c, "form.type", ["name", "display_name", "code"])
        assert "display_name" in result

    def test_empty_preferred_gets_defaults(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "create_date": {"type": "datetime"},
        }
        result = safe_fields(c, "form.type", ["nonexistent_field"])
        assert "display_name" in result

    def test_always_include(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "id": {"type": "integer"},
            "display_name": {"type": "char"},
            "name": {"type": "char"},
        }
        result = safe_fields(c, "test.model", ["name"], always_include=["display_name"])
        assert result[0] == "display_name"
        assert "name" in result


class TestClassifyFields:
    def test_classification(self):
        fields = {
            "name": {"type": "char", "string": "Name", "store": True},
            "state": {"type": "selection", "string": "State", "store": True},
            "partner_id": {"type": "many2one", "string": "Partner", "store": True, "relation": "res.partner"},
            "date_start": {"type": "date", "string": "Start Date", "store": True},
            "amount": {"type": "float", "string": "Amount", "store": True},
            "active": {"type": "boolean", "string": "Active", "store": True},
        }
        result = classify_fields(fields)
        assert "name" in result["identifiers"]
        assert "state" in result["states"]
        assert "partner_id" in result["relations"]
        assert "date_start" in result["dates"]
        assert "amount" in result["amounts"]


class TestGetModelFields:
    def test_returns_fields_on_success(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "name": {
                "type": "char",
                "string": "Name",
                "required": False,
                "readonly": False,
                "store": True,
                "relation": "",
            },
        }
        result = get_model_fields(c, "res.partner", use_cache=False)
        assert "name" in result
        assert result["name"]["type"] == "char"

    def test_returns_empty_dict_on_error(self):
        c = MagicMock()
        c.execute_kw.side_effect = Exception("RPC error")
        result = get_model_fields(c, "nonexistent.model", use_cache=False)
        assert result == {}


class TestDevGenerateCmd:
    def test_import(self):
        from kctl_odoo.commands.dev import generate_cmd

        assert callable(generate_cmd)


class TestDevModelFields:
    def test_import(self):
        from kctl_odoo.commands.dev import model_fields_cmd

        assert callable(model_fields_cmd)
