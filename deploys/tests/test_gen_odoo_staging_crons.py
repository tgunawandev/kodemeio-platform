"""Staging Odoo must never run crons.

A staging instance is restored from a production dump. `kctl-dokploy backups
pull` neutralises it -- ir_cron.active=false, mail servers off, uuid scrambled
-- and then the redeploy runs `-u`, which RELOADS each module's ir.cron XML and
sets active back to True. Measured on mac-odoo-erp-stg 2026-08-15: 13 crons
active again immediately after a clean neutralisation, every one of them
module-provided, nextcall stamped at the minute the module update ran. Among
them were writers: the SVL/GL invariant monitor, bank-reconciliation drift
detection, and fleet document-number reconciliation.

Disabling the records cannot win that race, because the race re-enables them.
Removing the cron THREADS does: with max_cron_threads=0 the odoo-cron container
starts and stays idle, so an active ir_cron row is inert. compose/odoo.prod.yml
already hardcodes 0 for odoo-web and odoo-gevent and takes the cron container's
value from ODOO_MAX_CRON_THREADS.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TENANT = {
    "code": "mac",
    "name": "Mandiri Agro",
    "short_name": "MAC",
    "domain": "idtpp.com",
}
ODOO_ENTRY = {"recipe": "erp", "short": "erp", "description": "ERP", "workers": 2, "apps": ["erp"]}


def _overrides(env_name: str, suffix: str, db_suffix: str) -> dict:
    from generate import gen_odoo

    _, content, _, _ = gen_odoo(
        TENANT,
        ODOO_ENTRY,
        env_name=env_name,
        server="tpp-prod-02",
        dns_suffix=suffix,
        db_suffix=db_suffix,
    )
    import yaml

    return yaml.safe_load(content)["env_overrides"]


def test_staging_pins_cron_threads_to_zero() -> None:
    ov = _overrides("staging", "-stg", "_stg")
    assert ov["ODOO_MAX_CRON_THREADS"] == "0", (
        "staging must run zero cron threads -- neutralisation alone loses to the "
        "module update that re-activates module-provided ir.cron records"
    )


def test_production_is_left_alone() -> None:
    """Production must keep running its crons. This guard is staging-only."""
    ov = _overrides("production", "", "")
    assert "ODOO_MAX_CRON_THREADS" not in ov, (
        "production must not be pinned to 0 -- it would silently stop every scheduled job on the live ERP"
    )
