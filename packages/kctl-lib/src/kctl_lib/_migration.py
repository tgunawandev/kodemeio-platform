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

# Profiles to delete outright.
# Two groups: (1) test pollution written to the real user config by
# kctl-lib / kctl-redis tests; (2) stale duplicates where the canonical
# entry in RENAME_MAP holds the real credentials.
DROP_PROFILES: frozenset[str] = frozenset(
    {
        # Test pollution (kctl-redis / kctl-lib test suites wrote these).
        "settest",
        "setbad",
        "masktest",
        "shortpass",
        "longpass",
        "saved-profile",
        "full-profile",
        "myprofile",
        "show-test",
        "inttest",
        "active",
        "alpha",
        "beta",
        "prod",
        # Stale duplicates (placeholder api_key=admin; canonical renames hold the real key).
        "mac-erp",  # superseded by idtpp-mac-odoo-erp
        "odoo-hrms-mac",  # superseded by idtpp-mac-odoo-hrms
        "odoo-hrms-tpp",  # superseded by idtpp-tpp-odoo-hrms
    }
)


def apply_rename_and_drop(config: dict[str, Any]) -> dict[str, Any]:
    """Apply RENAME_MAP and DROP_PROFILES to a config dict.

    Returns a new dict; does not mutate the input.

    Raises:
        ValueError: if a rename target already exists as a distinct profile
            (would silently merge otherwise).
    """
    profiles = dict(config.get("profiles", {}))
    out: dict[str, Any] = {}

    for name, data in profiles.items():
        if name in DROP_PROFILES:
            continue
        new_name = RENAME_MAP.get(name, name)
        if new_name in out:
            raise ValueError(f"Rename collision for '{new_name}': already present (from profile '{name}')")
        out[new_name] = data

    return {**config, "profiles": out}


def dedupe_service_keys(config: dict[str, Any]) -> dict[str, Any]:
    """Remove duplicate service keys within each profile.

    Rules (from spec step 5 of migration):
        * `onepassword` → merged into `op`. If both exist, `op` wins.
          If only `onepassword` exists, it is renamed to `op`.
        * In the `kodemeio` profile only: `sentry` is dropped if it points
          at the same URL as `glitchtip` (it was a copy-pasted duplicate).
          A `sentry` block pointing at a different host is preserved.

    Returns a new dict; does not mutate the input.
    """
    profiles_out: dict[str, Any] = {}

    for profile_name, profile_data in config.get("profiles", {}).items():
        if not isinstance(profile_data, dict):
            profiles_out[profile_name] = profile_data
            continue

        new_profile = dict(profile_data)

        # Rule 1: onepassword → op.
        if "onepassword" in new_profile:
            legacy = new_profile.pop("onepassword")
            if "op" not in new_profile:
                new_profile["op"] = legacy

        # Rule 2: drop duplicate sentry in kodemeio.
        if profile_name == "kodemeio":
            sentry = new_profile.get("sentry")
            glitchtip = new_profile.get("glitchtip")
            if isinstance(sentry, dict) and isinstance(glitchtip, dict) and sentry.get("url") == glitchtip.get("url"):
                new_profile.pop("sentry")

        profiles_out[profile_name] = new_profile

    return {**config, "profiles": profiles_out}


def strip_default_profile(config: dict[str, Any]) -> dict[str, Any]:
    """Remove the top-level `default_profile` key.

    Stage B removes the fallback in `kctl_lib.config.resolve_active_profile_name`;
    here we just strip the key from the file.
    """
    return {k: v for k, v in config.items() if k != "default_profile"}
