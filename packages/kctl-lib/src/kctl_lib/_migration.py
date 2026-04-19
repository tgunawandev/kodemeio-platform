"""Internal profile-migration logic for Stage A cleanup.

This module is intentionally marked private (leading underscore). In Stage B
of the profile standardization work it will be promoted into the public
`kctl-profiles` meta-CLI.
"""

from __future__ import annotations

from typing import Any

MigrationResult = dict[str, Any]

# Canonical keepers: old profile name → new profile name.
# See spec "Migration plan" step 3 for the full table.
RENAME_MAP: dict[str, str] = {
    # TPP Odoo
    "tpp-odoo-erp": "idtpp-tpp-odoo-erp",
    "tpp-odoo-hrms": "idtpp-tpp-odoo-hrms",
    "stg-tpp-odoo-erp": "idtpp-tpp-odoo-erp-stg",
    "stg-tpp-odoo-hrms": "idtpp-tpp-odoo-hrms-stg",
    "odoo-trad-tpp": "idtpp-tpp-odoo-trad",
    # MAC Odoo
    "mac-odoo-erp": "idtpp-mac-odoo-erp",
    "mac-odoo-hrms": "idtpp-mac-odoo-hrms",
    "odoo-dist-mac": "idtpp-mac-odoo-dist",
    # MAC dedicated infra
    "mac-prod": "idtpp-mac-postgres",
    "mac": "idtpp-mac",
    # ABCFood
    "abcfood-tmi": "abcfood-tmi-odoo",
    # Kodemeio
    "odoo-full-kod": "kodemeio-kod-odoo-full",
    # Local-dev Odoo
    "odoo_full": "local-odoo-full",
    "odoo_hrms": "local-odoo-hrms",
    "odoo_found": "local-odoo-found",
    "local-tpp": "local-odoo-tpp",
    "dev": "local-odoo-dev",
}
