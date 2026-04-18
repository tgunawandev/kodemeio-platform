"""Unit tests for the `kctl-odoo logs tail` command and its filter helpers."""

from __future__ import annotations

import re

import pytest

from kctl_odoo.commands.logs import (
    _LEVEL_RANK,
    _build_local_cmd,
    _build_remote_cmd,
    _is_local_url,
    _line_matches,
)

# ---------------------------------------------------------------------------
# _is_local_url
# ---------------------------------------------------------------------------


class TestIsLocalUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8069",
            "http://127.0.0.1:8069",
            "https://host.docker.internal",
            "http://localhost",
        ],
    )
    def test_local_urls(self, url: str) -> None:
        assert _is_local_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://tpp-odoo-erp.idtpp.com",
            "https://mac-odoo-erp.idtpp.com",
            "http://10.0.0.2:8069",
            "",
        ],
    )
    def test_remote_and_empty_urls(self, url: str) -> None:
        assert _is_local_url(url) is False


# ---------------------------------------------------------------------------
# _line_matches — the filter engine
# ---------------------------------------------------------------------------


SAMPLE = "2026-04-18 10:30:45,123 12 INFO mydb odoo.addons.account.move: posted AR123"
WARNING_LINE = "2026-04-18 10:30:46,000 14 WARNING mydb odoo.http: slow response"
ERROR_LINE = "2026-04-18 10:30:47,000 14 ERROR mydb odoo.sql_db: connection reset"
TRACEBACK = '  File "odoo/api.py", line 42, in run'


class TestLineMatches:
    def test_no_filters_keeps_all(self) -> None:
        assert _line_matches(SAMPLE, module=None, request=None, worker=None, min_level=None, grep=None) is True

    def test_non_odoo_line_kept_by_default(self) -> None:
        # Traceback continuations don't match the regex — they should pass through.
        assert _line_matches(TRACEBACK, module=None, request=None, worker=None, min_level=None, grep=None) is True

    def test_module_filter_matches_substring(self) -> None:
        assert _line_matches(SAMPLE, module="account.move", request=None, worker=None, min_level=None, grep=None)

    def test_module_filter_rejects_mismatch(self) -> None:
        assert not _line_matches(SAMPLE, module="stock.picking", request=None, worker=None, min_level=None, grep=None)

    def test_worker_filter_by_pid(self) -> None:
        assert _line_matches(SAMPLE, module=None, request=None, worker="12", min_level=None, grep=None)
        assert not _line_matches(SAMPLE, module=None, request=None, worker="99", min_level=None, grep=None)

    def test_request_id_in_message(self) -> None:
        assert _line_matches(SAMPLE, module=None, request="AR123", worker=None, min_level=None, grep=None)
        assert not _line_matches(SAMPLE, module=None, request="ZZZ", worker=None, min_level=None, grep=None)

    def test_min_level_at_warning_keeps_warning_and_error(self) -> None:
        wlvl = _LEVEL_RANK["WARNING"]
        assert _line_matches(WARNING_LINE, module=None, request=None, worker=None, min_level=wlvl, grep=None)
        assert _line_matches(ERROR_LINE, module=None, request=None, worker=None, min_level=wlvl, grep=None)
        assert not _line_matches(SAMPLE, module=None, request=None, worker=None, min_level=wlvl, grep=None)

    def test_grep_regex(self) -> None:
        pat = re.compile(r"slow|reset")
        assert _line_matches(WARNING_LINE, module=None, request=None, worker=None, min_level=None, grep=pat)
        assert _line_matches(ERROR_LINE, module=None, request=None, worker=None, min_level=None, grep=pat)
        assert not _line_matches(SAMPLE, module=None, request=None, worker=None, min_level=None, grep=pat)

    def test_grep_on_non_odoo_line(self) -> None:
        # When the line doesn't parse, grep still applies.
        pat = re.compile(r"api\.py")
        assert _line_matches(TRACEBACK, module=None, request=None, worker=None, min_level=None, grep=pat)
        pat_miss = re.compile(r"nope")
        assert not _line_matches(TRACEBACK, module=None, request=None, worker=None, min_level=None, grep=pat_miss)

    def test_combined_filters_are_AND(self) -> None:
        assert _line_matches(
            SAMPLE, module="account", request="AR123", worker="12", min_level=_LEVEL_RANK["INFO"], grep=None
        )
        # Change worker so it's now a mismatch.
        assert not _line_matches(
            SAMPLE, module="account", request="AR123", worker="99", min_level=_LEVEL_RANK["INFO"], grep=None
        )


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------


class TestBuildLocalCmd:
    """LocalClient.compose_cmd may prepend `-f <file>` (compose file flag); we test
    the stream-follow flag by inspecting the arg order after `logs`."""

    def test_adds_follow_and_service(self) -> None:
        cmd = _build_local_cmd(lines=50, follow=True, service="odoo-web")
        assert "logs" in cmd
        after_logs = cmd[cmd.index("logs") + 1 :]
        # After 'logs', we should see --tail=N, then -f (follow), then service.
        assert "--tail=50" in after_logs
        assert "-f" in after_logs  # follow flag (distinct from compose `-f file`)
        assert "odoo-web" in after_logs

    def test_no_follow_omits_flag(self) -> None:
        cmd = _build_local_cmd(lines=100, follow=False, service="odoo-web")
        assert "logs" in cmd
        after_logs = cmd[cmd.index("logs") + 1 :]
        # Follow flag must NOT appear after `logs` when follow=False.
        assert "-f" not in after_logs
        assert "--tail=100" in after_logs
        assert "odoo-web" in after_logs


class TestBuildRemoteCmd:
    def test_shape_with_follow(self) -> None:
        cmd = _build_remote_cmd(
            dokploy_profile="tpp-odoo-erp",
            compose_id="Qki8U2u4Ltstq0_6zW7UE",
            service="odoo-web",
            lines=200,
            follow=True,
        )
        assert cmd[0] == "kctl-dokploy"
        assert cmd[1:4] == ["--profile", "tpp-odoo-erp", "compose"]
        assert "service-logs" in cmd
        assert "Qki8U2u4Ltstq0_6zW7UE" in cmd
        assert "--service" in cmd and "odoo-web" in cmd
        assert "--tail" in cmd and "200" in cmd
        assert "-f" in cmd

    def test_no_follow_omits_flag(self) -> None:
        cmd = _build_remote_cmd(dokploy_profile="idtpp", compose_id="X", service="odoo-web", lines=100, follow=False)
        assert "-f" not in cmd
