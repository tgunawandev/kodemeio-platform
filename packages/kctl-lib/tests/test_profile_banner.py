"""Tests for profile_banner() in kctl_lib.output."""

from __future__ import annotations


class TestProfileBanner:
    def test_renders_single_profile(self) -> None:
        from kctl_lib.output import profile_banner

        rendered = profile_banner(
            app="kctl-odoo",
            profile="idtpp",
            inheritance_chain=["idtpp"],
            service_summary="https://odoo.idtpp.com (db: prod)",
        )
        assert "kctl-odoo" in rendered
        assert "idtpp" in rendered
        assert "https://odoo.idtpp.com" in rendered

    def test_renders_inheritance_arrow(self) -> None:
        from kctl_lib.output import profile_banner

        rendered = profile_banner(
            app="kctl-odoo",
            profile="idtpp-tpp-odoo-erp",
            inheritance_chain=["idtpp-tpp-odoo-erp", "idtpp"],
            service_summary="https://tpp-odoo-erp.idtpp.com (db: tpp_odoo_erp)",
        )
        assert "idtpp-tpp-odoo-erp" in rendered
        assert "idtpp" in rendered
        # The chain should show an arrow between active and parent.
        assert "←" in rendered

    def test_service_summary_optional(self) -> None:
        from kctl_lib.output import profile_banner

        rendered = profile_banner(
            app="kctl-profiles",
            profile="idtpp",
            inheritance_chain=["idtpp"],
            service_summary=None,
        )
        assert "kctl-profiles" in rendered
        assert "idtpp" in rendered
