"""Tests for the kctl-odoo service schema."""

from __future__ import annotations

import pytest


class TestOdooSchema:
    def test_accepts_valid_config(self) -> None:
        from kctl_odoo.schema import OdooServiceConfig

        ok = OdooServiceConfig(
            url="https://odoo.example.com",
            database="mydb",
            username="admin",
            api_key="k",
        )
        assert ok.database == "mydb"

    def test_rejects_missing_required(self) -> None:
        from pydantic import ValidationError

        from kctl_odoo.schema import OdooServiceConfig

        with pytest.raises(ValidationError):
            OdooServiceConfig(url="https://odoo.example.com")  # type: ignore[call-arg]

    def test_registered_under_odoo_key(self) -> None:
        from kctl_lib.schemas import get_schema

        # Importing kctl_odoo triggers registration (package __init__).
        import kctl_odoo  # noqa: F401

        assert get_schema("odoo") is not None
        assert get_schema("odoo").__name__ == "OdooServiceConfig"
