"""Prefix-inheritance chain resolver (Stage B)."""

from __future__ import annotations


class TestInheritanceChain:
    def test_single_segment_returns_just_self(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp") == ["idtpp"]

    def test_multi_segment_walks_back(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp-tpp-odoo-erp") == [
            "idtpp-tpp-odoo-erp",
            "idtpp-tpp-odoo",
            "idtpp-tpp",
            "idtpp",
        ]

    def test_staging_suffix_walks_back(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp-tpp-odoo-erp-stg") == [
            "idtpp-tpp-odoo-erp-stg",
            "idtpp-tpp-odoo-erp",
            "idtpp-tpp-odoo",
            "idtpp-tpp",
            "idtpp",
        ]

    def test_empty_profile_name_raises(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        try:
            resolve_inheritance_chain("")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError on empty profile name")
