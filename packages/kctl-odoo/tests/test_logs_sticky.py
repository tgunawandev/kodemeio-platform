"""Tests for the sticky-block traceback-capture behavior in `logs tail`.

When a matched line is a timestamped Odoo log header, all continuation lines
(indented traceback frames, SQL fragments, exception messages without a new
timestamp) must also be emitted — otherwise ERROR filters strip the actual
traceback body and the output is useless for debugging.
"""

from __future__ import annotations

import re
import subprocess
from unittest.mock import MagicMock, patch

from kctl_odoo.commands.logs import _LEVEL_RANK, _stream

# A realistic production sequence: INFO request, then an ERROR with a
# multi-line Python traceback, then back to INFO.
STREAM = """\
2026-04-18 08:19:06,000 48 INFO tpp odoo.http: GET /web 200 12ms
2026-04-18 08:19:07,121 54 ERROR tpp odoo.http: Exception during request handling.
Traceback (most recent call last):
  File "/opt/odoo/src/odoo/addons/bus/websocket.py", line 929, in open_connection
    socket = request.httprequest._HTTPRequest__environ['socket']
             ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
KeyError: 'socket'
2026-04-18 08:19:08,060 48 INFO tpp odoo.http: GET /web 200 9ms
2026-04-18 08:19:09,317 54 WARNING tpp odoo.sql_db: slow query 3.2s
"""


def _run_stream(
    stream_text: str,
    *,
    module: str | None = None,
    request: str | None = None,
    worker: str | None = None,
    min_level: int | None = None,
    grep: re.Pattern[str] | None = None,
) -> str:
    """Run _stream() against in-memory text and capture printed output."""
    lines = stream_text.splitlines(keepends=True)
    fake_proc = MagicMock()
    fake_proc.stdout = iter(lines)
    fake_proc.poll.return_value = 0  # already finished

    captured: list[str] = []

    def fake_print(line: str, end: str = "\n", highlight: bool = False) -> None:
        captured.append(line if end == "" else f"{line}{end}")

    with (
        patch.object(subprocess, "Popen", return_value=fake_proc),
        patch("kctl_odoo.commands.logs.console.print", side_effect=fake_print),
    ):
        _stream(
            ["docker", "logs", "-f", "fake"],
            cwd=None,
            module=module,
            request=request,
            worker=worker,
            min_level=min_level,
            grep=grep,
        )
    return "".join(captured)


class TestStickyTraceback:
    def test_error_filter_captures_full_traceback(self) -> None:
        # Filter: only ERROR+. Without sticky blocks, we'd lose the Traceback body.
        out = _run_stream(STREAM, min_level=_LEVEL_RANK["ERROR"])
        # The ERROR header line must be present.
        assert "ERROR tpp odoo.http: Exception during request handling." in out
        # AND every continuation line of that traceback must also be present.
        assert "Traceback (most recent call last):" in out
        assert 'File "/opt/odoo/src/odoo/addons/bus/websocket.py"' in out
        assert "KeyError: 'socket'" in out
        assert "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" in out
        # And the INFO/WARNING records either side must be dropped.
        assert "GET /web 200 12ms" not in out
        assert "slow query 3.2s" not in out

    def test_warning_filter_keeps_warning_but_not_info(self) -> None:
        out = _run_stream(STREAM, min_level=_LEVEL_RANK["WARNING"])
        assert "ERROR tpp odoo.http: Exception" in out
        assert "KeyError: 'socket'" in out  # still inside the traceback block
        assert "WARNING tpp odoo.sql_db: slow query 3.2s" in out
        assert "GET /web 200 12ms" not in out

    def test_grep_on_continuation_line_opens_block(self) -> None:
        # Grep for a filename that only appears INSIDE the traceback body.
        out = _run_stream(STREAM, grep=re.compile(r"websocket\.py"))
        # The line with the filename must be emitted.
        assert "websocket.py" in out
        # Subsequent continuation lines of the same traceback should also flow.
        assert "KeyError: 'socket'" in out

    def test_non_matching_stream_produces_nothing(self) -> None:
        out = _run_stream(STREAM, grep=re.compile(r"nonexistent"))
        assert out == ""

    def test_back_to_back_errors_both_captured(self) -> None:
        # Real Odoo logs always have millisecond suffix — include it so the
        # timestamp regex recognizes each line as a new header.
        double = (
            "2026-04-18 08:19:07,000 54 ERROR tpp odoo.http: first err\n"
            "  File 'a.py', line 1, in f\n"
            "Exception: one\n"
            "2026-04-18 08:19:08,000 54 ERROR tpp odoo.http: second err\n"
            "  File 'b.py', line 1, in g\n"
            "Exception: two\n"
            "2026-04-18 08:19:09,000 54 INFO tpp odoo.http: ok\n"
        )
        out = _run_stream(double, min_level=_LEVEL_RANK["ERROR"])
        assert "first err" in out
        assert "Exception: one" in out
        assert "second err" in out
        assert "Exception: two" in out
        assert "INFO tpp odoo.http: ok" not in out
