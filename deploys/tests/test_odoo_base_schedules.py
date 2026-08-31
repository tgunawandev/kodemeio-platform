"""Guards for the Odoo base's schedules block.

Both assertions encode a bug that ran in production for five months:

1. `service: odoo` matched no container. The real compose services are
   odoo-web / odoo-cron / odoo-gevent. Dokploy resolves
   {compose.appName}-{serviceName}-1, and an unmatched name yields an empty
   string, so it ran `docker exec  bash -c ...` and Docker read `bash` as the
   container name.
2. `DELETE FROM ir_sessions` targeted a table that does not exist. Odoo 18
   here runs the session_db server-wide module, whose table is
   http_sessions(sid, write_date, payload).
"""

from __future__ import annotations

from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1] / "bases" / "odoo.yaml"
REAL_SERVICES = {"odoo-web", "odoo-cron", "odoo-gevent"}


def _schedules() -> list[dict]:
    return yaml.safe_load(BASE.read_text())["schedules"]


def test_every_schedule_targets_a_real_compose_service():
    for sched in _schedules():
        assert sched["service"] in REAL_SERVICES, (
            f"{sched['name']}: service {sched['service']!r} matches no compose service. "
            f"Dokploy resolves an unmatched name to an empty string and silently "
            f"runs `docker exec  <shell>`, which fails every time. Real services: {sorted(REAL_SERVICES)}"
        )


def test_session_cleanup_is_invoked_as_a_script_not_inline_sql():
    """The cleanup cannot be inline SQL -- see test_no_command_contains_shell_metacharacters.

    It needs a comparison (<), an interval (quotes) and a function (parens),
    all three of which Dokploy passes through unescaped and all three of which
    kill the run before it produces any output. The SQL therefore lives in
    kodemeio-odoo at scripts/session-cleanup.sh, baked into the image at
    /opt/odoo/scripts/, and the schedule just invokes it.

    The correct table name (http_sessions, created by session_db -- ir_sessions
    does not exist in Odoo 18) is asserted inside that script, not here.
    """
    cleanup = [s for s in _schedules() if "session-cleanup" in s["name"]]
    assert cleanup, "the session-cleanup schedule disappeared from the base"
    for sched in cleanup:
        assert sched["command"] == "bash /opt/odoo/scripts/session-cleanup.sh", (
            "session cleanup must invoke the baked-in script; inline SQL cannot work "
            f"through Dokploy. Command: {sched['command']}"
        )
        assert "psql" not in sched["command"], "inline psql reintroduces the metacharacter problem"


SHELL_METACHARACTERS = ["'", "(", ")", "<", ">", "|", "&", ";", "$", "`"]


def test_no_command_contains_shell_metacharacters():
    """Dokploy does not escape shell metacharacters in schedule commands.

    Established by single-character bisection against live Dokploy on
    2026-08-31, on mac-odoo-erp-session-cleanup:

        psql ... -tAc "SELECT 1 WHERE 1 = 1"   -> status: done
        psql ... -tAc "SELECT 1 WHERE 1 < 2"   -> status: error
        psql ... -tAc "SELECT count(*) ..."    -> status: error
        psql ... -c "... INTERVAL '7 days'"    -> status: error

    A command containing one of these fails before Dokploy logs its "Running
    command:" line, leaving a 22-byte log reading only "Initializing
    schedule" -- no error text anywhere, and no alert, because Dokploy has no
    failure notification for scheduled jobs.

    Double quotes ARE safe: `bash -lc "echo probe"` runs fine.

    Practical consequence: a command needing a comparison, a function call or
    a quoted literal cannot be expressed inline. It has to live in a script
    inside the image and be invoked with a metacharacter-free command.
    """
    for sched in _schedules():
        found = [c for c in SHELL_METACHARACTERS if c in sched["command"]]
        assert not found, (
            f"{sched['name']}: command contains shell metacharacter(s) {found}, which "
            f"Dokploy passes through unescaped -- the run fails with an empty log and "
            f"no alert. Command: {sched['command']}"
        )
