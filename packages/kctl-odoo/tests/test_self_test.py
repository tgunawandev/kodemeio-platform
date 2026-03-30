"""Tests for self_test smoke test definitions."""

from __future__ import annotations

from kctl_odoo.commands.self_test import SMOKE_TESTS


class TestSmokeTestDefinitions:
    """Verify SMOKE_TESTS dict references valid commands."""

    def test_no_troubleshoot_references(self) -> None:
        """No smoke test should reference the old 'troubleshoot' group."""
        for group, cmd in SMOKE_TESTS.items():
            if cmd is not None:
                assert not cmd.startswith("troubleshoot "), (
                    f"Group '{group}' uses removed 'troubleshoot' command: {cmd}. Use 'doctor' instead."
                )

    def test_no_biz_references(self) -> None:
        """No smoke test should reference the removed 'biz' group."""
        assert "biz" not in SMOKE_TESTS, "Group 'biz' was removed. Use 'dashboard kpi' instead."

    def test_no_profiles_references(self) -> None:
        """No smoke test should reference the removed 'profiles' group."""
        assert "profiles" not in SMOKE_TESTS, "Group 'profiles' was merged into 'config profiles'."

    def test_health_uses_doctor(self) -> None:
        """The 'health' smoke test should use 'doctor check'."""
        assert SMOKE_TESTS["health"] == "doctor check"

    def test_server_uses_correct_subcommand(self) -> None:
        """The 'server' smoke test should use 'server params'."""
        cmd = SMOKE_TESTS["server"]
        assert cmd.startswith("server params"), f"Expected 'server params ...', got: {cmd}"

    def test_integration_uses_correct_subcommand(self) -> None:
        """The 'integration' smoke test should use 'integration webhooks'."""
        assert SMOKE_TESTS["integration"] == "integration webhooks"

    def test_tax_uses_correct_subcommand(self) -> None:
        """The 'tax' smoke test should use 'tax accounts'."""
        assert SMOKE_TESTS["tax"] == "tax accounts"

    def test_all_groups_have_commands_or_none(self) -> None:
        """Every entry must be a string command or None (skip)."""
        for group, cmd in SMOKE_TESTS.items():
            assert cmd is None or isinstance(cmd, str), f"Group '{group}' has invalid entry type: {type(cmd)}"

    def test_missing_groups_added(self) -> None:
        """New command groups from SP4 should have smoke tests."""
        expected_groups = [
            "doctor",
            "views",
            "manifest",
            "orm",
            "record-rules",
            "traceback",
            "translations",
        ]
        for group in expected_groups:
            assert group in SMOKE_TESTS, f"Missing smoke test for group: {group}"
