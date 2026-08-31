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


def test_session_cleanup_targets_the_real_table():
    cleanup = [s for s in _schedules() if "session-cleanup" in s["name"]]
    assert cleanup, "the session-cleanup schedule disappeared from the base"
    for sched in cleanup:
        assert "http_sessions" in sched["command"], (
            "session cleanup must target http_sessions (created by the session_db "
            "server-wide module), not ir_sessions, which does not exist"
        )
        assert "ir_sessions" not in sched["command"]
