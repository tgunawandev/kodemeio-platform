#!/usr/bin/env python3
"""Generate deploy instance YAMLs and env files from tenant manifests.

Usage:
    python generate.py                    # Generate all tenants
    python generate.py --tenant mac       # Generate single tenant
    python generate.py --dry-run          # Preview without writing
    python generate.py --diff             # Show diff vs existing files
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import yaml

DEPLOY_DIR = Path(__file__).parent
TENANTS_DIR = DEPLOY_DIR / "tenants"
INSTANCES_DIR = DEPLOY_DIR / "instances"
ENV_DIR = DEPLOY_DIR / "env"

HEADER = "# GENERATED FROM tenants/{code}.yaml — DO NOT EDIT\n"

# ---------------------------------------------------------------------------
# Recipe table — maps high-level recipe names (used in tenants/*.yaml under
# `odoo:` entries as `recipe: <name>`) to (profile, extras) pairs that
# materialize as ODOO_DEPLOY_PROFILE + ODOO_INSTALL_BUNDLE in generated env files.
#
# Single source of truth — must stay in sync with:
#   kodemeio-odoo/install/README.md
#   kodemeio-odoo/.env.example
#   kodemeio-odoo/scripts/verify-profile-migration.sh
# ---------------------------------------------------------------------------
ODOO_RECIPES: dict[str, tuple[str, str]] = {
    # recipe_name: (profile, extras_csv_for_ODOO_INSTALL_BUNDLE)
    "erp": ("erp", ""),
    "hrms": ("hrms", ""),
    "import": ("erp", ""),
    "distribution": (
        "erp",
        "private-field-ops,private-desktop-apps:dms,private-retail:shop,private-analytics",
    ),
    "manufacturing": (
        "erp",
        "private-mrp,private-sfa,private-desktop-apps:tpm,private-analytics",
    ),
    "retail": ("erp", "oca-pos,private-retail"),
    "trading": ("erp", "private-analytics"),
    "import-hrms": ("erp", "private-hr-full"),
    "distribution-hrms": (
        "erp",
        "private-field-ops,private-desktop-apps:dms,private-retail:shop,private-analytics,private-hr-full",
    ),
    "manufacturing-hrms": (
        "erp",
        "private-mrp,private-sfa,private-desktop-apps:tpm,private-analytics,private-hr-full",
    ),
    "retail-hrms": ("erp", "oca-pos,private-retail,private-hr-full"),
    "full": (
        "erp",
        "core-hr,core-maintenance,core-fleet,oca-report,oca-hr,oca-maintenance,oca-pos,oca-saas,private-finance-hr,private-form,private-sfa,private-lfa,private-mrp,private-hrm,private-desktop-apps,private-retail,private-analytics,private-asset,private-recruitment,private-saas",
    ),
}


def resolve_recipe(recipe_or_profile: str) -> tuple[str, str]:
    """Resolve a tenant `recipe:` (preferred) or legacy `profile:` value to
    (deploy_profile, install_bundle_extras).

    Accepts both new recipe names (`distribution`, `manufacturing`, …) and
    legacy profile names (same strings, since recipes are named after the
    profiles they replace) so old tenant YAMLs keep working during rollout.
    """
    if recipe_or_profile not in ODOO_RECIPES:
        raise ValueError(
            f"Unknown odoo recipe {recipe_or_profile!r}. Valid: {sorted(ODOO_RECIPES.keys())}"
        )
    return ODOO_RECIPES[recipe_or_profile]


# ---------------------------------------------------------------------------
# Naming convention: {tenant}-{stack}-{app}
#
#   Filename:      {tenant}-{stack}-{app}.yaml
#   instance.name: {tenant}-{stack}-{app}
#   DNS name:      {tenant}-{app}{dns_suffix}.{domain}
#   Database:      {tenant}_{stack}_{app}{db_suffix}
#   Env file:      .env.{tenant}-{stack}-{app}
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def yaml_dump(data: dict) -> str:
    return yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )


def load_tenant(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Instance generators
# ---------------------------------------------------------------------------


def gen_react_pwa(
    tenant: dict,
    odoo_entry: dict,
    app: str,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
    db_suffix: str = "",
) -> tuple[str, str, str, str | None]:
    """Generate react-pwa instance YAML + env content.

    Returns (yaml_filename, yaml_content, env_filename, env_content).
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    short = odoo_entry["short"]
    app_upper = app.upper().replace("-", "_")

    # The unified `erp` PWA (@kodemeio/erp) calls /api/v1/base/modules and
    # /api/v1/{module}/... directly at the Odoo root, so its base URL is the
    # host without a path prefix. Per-app legacy PWAs embed /{app}/api.
    odoo_host = f"{code}-odoo-{short}{dns_suffix}.{domain}"
    if app == "erp":
        api_base_url = f"https://{odoo_host}"
    else:
        api_base_url = f"https://{odoo_host}/{app}/api"

    yaml_filename = f"{code}-react-{app}.yaml"
    env_filename = f".env.{code}-react-{app}"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/react-pwa.yaml",
        "instance": {
            "name": f"{code}-react-{app}",
            "description": f"{display} — {app_upper} PWA",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "source_overrides": {
                "compose_path": f"compose/docker-compose.{app}.yml",
            },
            "dns": {
                "zone": domain,
                "name": f"{code}-{app}{dns_suffix}",
            },
            "domain": {
                "host": f"{code}-{app}{dns_suffix}.{domain}",
                "port": 80,
                "service": app,
                "https": True,
            },
            "env_file": f"../../env/{env_name}/{env_filename}",
            "env_overrides": {
                f"VITE_{app_upper}_APP_NAME": f"{display} {app_upper}",
                f"VITE_{app_upper}_API_BASE_URL": api_base_url,
            },
        }
    )

    host = f"{code}-{app}{dns_suffix}.{domain}"
    slug = f"{code}-react-{app}"
    env_content = (
        f"VITE_{app_upper}_APP_NAME={display} {app_upper}\n"
        f"VITE_{app_upper}_API_BASE_URL={api_base_url}\n"
        f"VITE_AUTH_MODE=oidc\n"
        f"VITE_OIDC_AUTHORITY=https://auth.kodeme.io/application/o/{slug}/\n"
        f"VITE_{app_upper}_OIDC_CLIENT_ID=\n"
        f"VITE_{app_upper}_OIDC_REDIRECT_URI=https://{host}/auth/callback\n"
        f"VITE_{app_upper}_THEME={app}\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_odoo(
    tenant: dict,
    odoo_entry: dict,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
    db_suffix: str = "",
) -> tuple[str, str, str, str]:
    """Generate odoo instance YAML + env.example content.

    Returns (yaml_filename, yaml_content, env_example_filename, env_example_content).
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    # Accept new `recipe:` key (preferred) or legacy `profile:` key.
    # Both resolve through ODOO_RECIPES, so legacy tenant YAMLs keep working.
    recipe_name = odoo_entry.get("recipe") or odoo_entry["profile"]
    deploy_profile, install_extras = resolve_recipe(recipe_name)
    short = odoo_entry["short"]
    description = odoo_entry.get("description", recipe_name)
    workers = odoo_entry.get("workers", 4)
    db_name = f"{code}_odoo_{short}{db_suffix}"
    dns_name = f"{code}-odoo-{short}{dns_suffix}"
    host = f"{code}-odoo-{short}{dns_suffix}.{domain}"

    yaml_filename = f"{code}-odoo-{short}.yaml"
    env_example_filename = f".env.{code}-odoo-{short}.example"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/odoo.yaml",
        "instance": {
            "name": f"{code}-odoo-{short}{dns_suffix}",
            "description": f"{display} — {description}",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "dns": {
                "zone": domain,
                "name": dns_name,
            },
            "domain": {
                "host": host,
                "port": 8069,
                "service": "odoo-web",
                "https": True,
                "cert": "letsencrypt",
            },
            "database": {
                "name": db_name,
                "user": "odoo",
            },
            "env_file": f"../../env/{env_name}/.env.{code}-odoo-{short}",
            "env_overrides": {
                "COMPOSE_PROJECT_NAME": f"{code}-odoo-{short}",
                "TENANT": code,
                "PGDATABASE": db_name,
                "PGUSER": "odoo",
                "ODOO_DB_FILTER": f"^{db_name}$",
                "DOMAIN": host,
                "ODOO_WORKERS": str(workers),
            },
            "post_deploy": {
                "odoo_profile": f"profile-{deploy_profile}",
                "odoo_install_bundle": install_extras,
                "recipe": recipe_name,
            },
        }
    )

    env_example = (
        f"# =============================================================================\n"
        f"# {display} {description} — {env_name.title()} Environment\n"
        f"# =============================================================================\n"
        f"# Instance: {host}\n"
        f"# Recipe:   {recipe_name}\n"
        f"# Profile:  {deploy_profile}\n"
        f"# Extras:   {install_extras or '(none)'}\n"
        f"# =============================================================================\n"
        f"\n"
        f"# PROJECT IDENTIFICATION\n"
        f"COMPOSE_PROJECT_NAME={code}-odoo-{short}\n"
        f"TENANT={code}\n"
        f"DOMAIN={host}\n"
        f"\n"
        f"# DATABASE\n"
        f"PGHOST=10.0.0.3\n"
        f"PGPORT=5432\n"
        f"PGUSER=odoo\n"
        f"PGPASSWORD=CHANGE_ME\n"
        f"PGDATABASE={db_name}\n"
        f"ODOO_DB_MAXCONN=32\n"
        f"\n"
        f"# ODOO CORE\n"
        f"ODOO_ADMIN_PASSWD=CHANGE_ME\n"
        f"ODOO_DB_FILTER=^{db_name}$\n"
        f"ODOO_DB_NAME={db_name}\n"
        f"ODOO_LIST_DB=False\n"
        f"ODOO_INIT_DB=true\n"
        f"RUNNING_ENV={env_name}\n"
        f"WITHOUT_DEMO=True\n"
        f"ODOO_HTTP_PORT=8069\n"
        f"ODOO_GEVENT_PORT=8072\n"
        f"ODOO_DATA_DIR=/var/lib/odoo\n"
        f"ODOO_LOG_LEVEL=warn\n"
        f"ODOO_SERVER_WIDE_MODULES=base,web,bus,bus_alt_connection,session_db,dbfilter_from_header\n"
        f"\n"
        f"# DEPLOY PROFILE\n"
        f"ODOO_DEPLOY_PROFILE={deploy_profile}\n"
        + (f"ODOO_INSTALL_BUNDLE={install_extras}\n" if install_extras else "")
        + f"ODOO_RUN_UPDATE=false\n"
        f"\n"
        f"# WORKERS\n"
        f"ODOO_WORKERS={workers}\n"
        f"ODOO_MAX_CRON_THREADS=2\n"
        f"ODOO_QUEUE_JOB_CHANNELS=root:2\n"
        f"\n"
        f"# RESOURCES\n"
        f"CPU_LIMIT=2\n"
        f"MEMORY_LIMIT=4G\n"
        f"CPU_LIMIT_CRON=1\n"
        f"MEMORY_LIMIT_CRON=1G\n"
        f"ODOO_LIMIT_MEMORY_SOFT=2147483648\n"
        f"ODOO_LIMIT_MEMORY_HARD=4294967296\n"
        f"ODOO_LIMIT_TIME_CPU=600\n"
        f"ODOO_LIMIT_TIME_REAL=1200\n"
        f"ODOO_LIMIT_TIME_REAL_CRON=1800\n"
        f"\n"
        f"# SMTP\n"
        f"SMTP_SERVER=mail.kodeme.io\n"
        f"SMTP_PORT=587\n"
        f"SMTP_USER={code}@kodeme.io\n"
        f"SMTP_PASSWORD=CHANGE_ME\n"
        f"SMTP_SSL=True\n"
        f"EMAIL_FROM={code}@kodeme.io\n"
        f"\n"
        f"# STORAGE\n"
        f"IR_ATTACHMENT_LOCATION=file\n"
        f"TZ=Asia/Jakarta\n"
        f"IMAGE_TAG=latest\n"
    )

    return yaml_filename, yaml_dump(instance), env_example_filename, env_example


def gen_nextjs_corporate(
    tenant: dict,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
) -> tuple[str, str, str, str]:
    """Generate Next.js corporate website instance YAML + env."""
    code = tenant["code"]
    name = tenant["name"]
    domain = tenant["domain"]
    compose_brand = tenant["_web_corporate_brand"]

    yaml_filename = f"{code}-nextjs-web.yaml"
    env_filename = f".env.{code}-nextjs-web"

    # Production uses "@" (apex), staging uses suffixed subdomain
    if dns_suffix:
        dns_name = f"{code}-web{dns_suffix}"
        host = f"{code}-web{dns_suffix}.{domain}"
    else:
        dns_name = "@"
        host = domain

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/nextjs.yaml",
        "instance": {
            "name": f"{code}-nextjs-web",
            "description": f"{name} company website",
        },
        "source_overrides": {
            "compose_path": f"compose/docker-compose.{compose_brand}.yml",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "dns": {
                "zone": domain,
                "name": dns_name,
            },
            "domain": {
                "host": host,
                "port": 3000,
                "service": f"{compose_brand}-web",
                "https": True,
                "cert": "letsencrypt",
            },
            "env_file": f"../../env/{env_name}/{env_filename}",
        }
    )

    env_content = (
        f"NODE_ENV=production\nNEXT_PUBLIC_SITE_URL=https://{host}\nTZ=Asia/Jakarta\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_nextjs_careers(
    tenant: dict,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
) -> tuple[str, str, str, str]:
    """Generate Next.js careers portal instance YAML + env."""
    code = tenant["code"]
    name = tenant["name"]
    domain = tenant["domain"]
    dns_name = f"{code}-careers{dns_suffix}"
    host = f"{code}-careers{dns_suffix}.{domain}"

    yaml_filename = f"{code}-nextjs-careers.yaml"
    env_filename = f".env.{code}-nextjs-careers"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/nextjs.yaml",
        "instance": {
            "name": f"{code}-nextjs-careers",
            "description": f"{name} — Careers Portal (recruitment)",
        },
        "source_overrides": {
            "compose_path": "compose/docker-compose.prod.careers.yml",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "healthcheck": {
                "port": 3000,
            },
            "dns": {
                "zone": domain,
                "name": dns_name,
            },
            "domain": {
                "host": host,
                "port": 3000,
                "service": "careers",
                "https": True,
            },
            "env_overrides": {
                "NEXT_PUBLIC_SITE_URL": f"https://{host}",
                "NEXT_PUBLIC_SITE_NAME": name,
                "NEXT_PUBLIC_COMPANY_WEBSITE": f"https://{domain}",
                "NEXT_PUBLIC_API_URL": f"https://{code}-odoo-hrms{dns_suffix}.{domain}",
                "NEXT_PUBLIC_RECRUITMENT_API_URL": f"https://{code}-odoo-hrms{dns_suffix}.{domain}/recruitment/api",
                "API_URL": f"https://{code}-odoo-hrms{dns_suffix}.{domain}",
            },
        }
    )

    env_content = (
        f"NODE_ENV=production\n"
        f"NEXT_PUBLIC_SITE_URL=https://{host}\n"
        f"NEXT_PUBLIC_SITE_NAME={name}\n"
        f"NEXT_PUBLIC_COMPANY_WEBSITE=https://{domain}\n"
        f"NEXT_PUBLIC_API_URL=https://{code}-odoo-hrms{dns_suffix}.{domain}\n"
        f"NEXT_PUBLIC_RECRUITMENT_API_URL=https://{code}-odoo-hrms{dns_suffix}.{domain}/recruitment/api\n"
        f"API_URL=https://{code}-odoo-hrms{dns_suffix}.{domain}\n"
        f"TZ=Asia/Jakarta\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def _read_env_var(env_path: Path, key: str) -> str | None:
    """Read a KEY=value line from an env file. Returns None if file or key missing."""
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return None


def gen_accurate_sync(
    tenant: dict,
    accurate_cfg: dict,
    odoo_entry: dict,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
    db_suffix: str = "",
) -> tuple[str, str, str, str]:
    """Generate accurate-sync instance YAML + env content.

    Returns (yaml_filename, yaml_content, env_filename, env_content).

    Secrets (PGPASSWORD, ODOO_ADMIN_PASSWD) are sourced from the sibling
    .env.{code}-odoo-{short} file when present — this keeps the accurate-sync
    env in lock-step with the Odoo instance it targets without duplicating
    the secret values in tenants/*.yaml. If the sibling file is missing or
    a key is absent, CHANGE_ME is emitted and the caller is expected to
    populate it via the Dokploy UI.
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    short = odoo_entry["short"]
    db_name = f"{code}_odoo_{short}{db_suffix}"
    odoo_host = f"{code}-odoo-{short}{dns_suffix}.{domain}"
    accurate_tenants = ",".join(accurate_cfg.get("tenants", [code]))
    image_tag = accurate_cfg.get("image_tag", "latest")

    # TRIGGER_SECRET — preserve existing value, else generate fresh.
    # Never rotate automatically (would break the Odoo→sync HTTP handshake).
    import secrets as _secrets

    _target_env_path = ENV_DIR / env_name / f".env.{code}-accurate-sync"
    _existing_secret = (
        _read_env_var(_target_env_path, "TRIGGER_SECRET")
        if _target_env_path.exists()
        else None
    )
    trigger_secret = _existing_secret or _secrets.token_hex(32)

    # Bridge the secret into the sibling Odoo container's env so the
    # accurate_integration post-migration hook can seed
    # ir.config_parameter.accurate_sync.trigger_secret on install/upgrade.
    # Env var name differs from the sync side to avoid collision:
    #   sync container  → TRIGGER_SECRET
    #   Odoo container  → ACCURATE_TRIGGER_SECRET
    sibling_env_path = ENV_DIR / env_name / f".env.{code}-odoo-{short}"
    if sibling_env_path.exists():
        existing_text = sibling_env_path.read_text()
        if "ACCURATE_TRIGGER_SECRET=" in existing_text:
            # Replace the existing value in-place (preserves surrounding comments)
            import re as _re

            new_text = _re.sub(
                r"^ACCURATE_TRIGGER_SECRET=.*$",
                f"ACCURATE_TRIGGER_SECRET={trigger_secret}",
                existing_text,
                flags=_re.MULTILINE,
            )
        else:
            # Append at end
            new_text = (
                existing_text.rstrip()
                + "\n"
                + "\n"
                + "# ACCURATE_TRIGGER_SECRET — mirrors TRIGGER_SECRET in\n"
                + f"# .env.{code}-accurate-sync; read by accurate_integration\n"
                + "# post-migration to populate ir.config_parameter.\n"
                + f"ACCURATE_TRIGGER_SECRET={trigger_secret}\n"
            )
        sibling_env_path.write_text(new_text)

    # Pull secrets + PGHOST from the sibling Odoo env file so we don't duplicate
    # them in tenants/*.yaml. Fallback to CHANGE_ME / default PGHOST when missing.
    sibling_env = ENV_DIR / env_name / f".env.{code}-odoo-{short}"
    pghost = _read_env_var(sibling_env, "PGHOST") or "10.0.0.3"
    pgpassword = _read_env_var(sibling_env, "PGPASSWORD") or "CHANGE_ME"
    odoo_admin_passwd = _read_env_var(sibling_env, "ODOO_ADMIN_PASSWD") or "CHANGE_ME"

    yaml_filename = f"{code}-accurate-sync.yaml"
    env_filename = f".env.{code}-accurate-sync"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/accurate-sync.yaml",
        "instance": {
            "name": f"{code}-accurate-sync",
            "description": f"{display} — Accurate Online sync worker",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "env_file": f"../../env/{env_name}/.env.{code}-accurate-sync",
            "env_overrides": {
                # COMPOSE_PROJECT_NAME intentionally omitted — Dokploy manages
                # the project namespace via its auto-generated random `appName`
                # suffix. Injecting this variable caused the 2026-04-16 outage
                # where deploys finished "done" but no containers came up.
                "TENANT": code,
                "PGDATABASE": db_name,
                "PGUSER": "odoo",
                "ODOO_URL": f"https://{odoo_host}",
                "ODOO_DB_FILTER": f"^{db_name}$",
                "ACCURATE_TENANTS": accurate_tenants,
                "IMAGE_TAG": image_tag,
            },
        }
    )

    env_content = (
        f"# =============================================================================\n"
        f"# {display} Accurate-Sync — {env_name.title()} Environment\n"
        f"# =============================================================================\n"
        f"# GENERATED from tenants/{code}.yaml (accurate_sync block).\n"
        f"# Secrets (PGPASSWORD, ODOO_ADMIN_PASSWD) are copied from the sibling\n"
        f"# .env.{code}-odoo-{short} file at generate time. Re-run generate.py\n"
        f"# after rotating those secrets to keep this file in sync.\n"
        f"# =============================================================================\n"
        f"\n"
        f"TENANT={code}\n"
        f"\n"
        f"# DATABASE — mirrors .env.{code}-odoo-{short}\n"
        f"PGHOST={pghost}\n"
        f"PGPORT=5432\n"
        f"PGUSER=odoo\n"
        f"PGPASSWORD={pgpassword}\n"
        f"PGDATABASE={db_name}\n"
        f"\n"
        f"# ODOO — URL of the sibling Odoo instance, admin password for RPC calls\n"
        f"ODOO_URL=https://{odoo_host}\n"
        f"ODOO_DB_FILTER=^{db_name}$\n"
        f"ODOO_ADMIN_PASSWD={odoo_admin_passwd}\n"
        f"\n"
        f"# TENANT LIST — comma-separated slugs from accurate_company table\n"
        f"ACCURATE_TENANTS={accurate_tenants}\n"
        f"\n"
        f"# IMAGE\n"
        f"IMAGE_TAG={image_tag}\n"
        f"TZ=Asia/Jakarta\n"
        f"\n"
        f"# TRIGGER_SECRET — shared secret for the HTTP /sync endpoint.\n"
        f"# The Odoo addon's ir.config_parameter.accurate_sync.trigger_secret\n"
        f"# must hold the SAME value (seeded via post-migration from the\n"
        f"# sibling Odoo container's ACCURATE_TRIGGER_SECRET env; Task 9 of\n"
        f"# the rollout plan bridges the two values).\n"
        f"TRIGGER_SECRET={trigger_secret}\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_ofelia(
    tenant: dict,
    scheduler: dict,
    env_name: str = "production",
    server: str = "",
) -> tuple[str, str, str, str]:
    """Generate Ofelia scheduler instance YAML + env.example.

    Each scheduler entry produces an independent Ofelia instance that loads
    a specific INI schedule file from the kodemeio-ofelia repo.
    """
    code = tenant["code"]
    name = tenant["name"]
    sched_name = scheduler["name"]
    schedule_file = scheduler["schedule_file"]

    yaml_filename = f"{code}-ofelia-{sched_name}.yaml"
    env_example_filename = f".env.{code}-ofelia-{sched_name}.example"
    container_name = f"{code}-ofelia-{sched_name}"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/ofelia.yaml",
        "instance": {
            "name": container_name,
            "description": f"{name} — Ofelia scheduler ({sched_name})",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "env_file": f"../../env/{env_name}/.env.{code}-ofelia-{sched_name}",
            "env_overrides": {
                "SCHEDULE_FILE": schedule_file,
                "CONTAINER_NAME": container_name,
            },
        }
    )

    config_host = scheduler.get("config_host", "/opt/kodemeio/config.yaml")
    env_example = (
        f"# Ofelia scheduler ({sched_name}) for {name}\n"
        f"SCHEDULE_FILE={schedule_file}\n"
        f"CONTAINER_NAME={container_name}\n"
        f"KODEMEIO_CONFIG_HOST={config_host}\n"
        f"TZ=Asia/Jakarta\n"
        f"OFELIA_TAG=latest\n"
    )

    return yaml_filename, yaml_dump(instance), env_example_filename, env_example


def gen_notify(
    tenant: dict,
    env_name: str = "production",
    server: str = "",
    dns_suffix: str = "",
) -> tuple[str, str, str, str]:
    """Generate notify service instance YAML + env.example."""
    code = tenant["code"]
    name = tenant["name"]
    domain = tenant["domain"]
    dns_name = f"{code}-notify{dns_suffix}"
    host = f"{code}-notify{dns_suffix}.{domain}"

    yaml_filename = f"{code}-hono-notify.yaml"
    env_example_filename = f".env.{code}-hono-notify.example"

    # Build ALLOWED_ORIGINS from all React PWA apps across all Odoo entries
    all_apps = []
    for odoo_entry in tenant.get("_odoo_entries", []):
        for app in odoo_entry.get("apps", []):
            all_apps.append(f"https://{code}-{app}{dns_suffix}.{domain}")
    allowed_origins = ",".join(all_apps)

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/infra.yaml",
        "instance": {
            "name": f"{code}-hono-notify",
            "description": "Notification dispatch service (FCM push + SSE real-time + Telegram)",
        },
        "source_overrides": {
            "type": "github",
            "owner": "tgunawandev",
            "repo": "kodemeio-react",
            "branch": "main",
            "compose_path": "apps/api/notify/docker-compose.yml",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    else:
        instance["server"] = "kodeme-service"
    instance.update(
        {
            "healthcheck": {
                "path": "/health",
                "port": 3020,
                "expected_status": 200,
                "timeout": 60,
                "interval": 10,
            },
            "dns": {
                "zone": domain,
                "name": dns_name,
            },
            "domain": {
                "host": host,
                "port": 3020,
                "service": "notify",
                "https": True,
            },
            "env_overrides": {
                "NODE_ENV": "production",
                "PORT": "3020",
                "DATABASE_URL": "postgresql://kodemeio:${DB_PASSWORD}@postgres:5432/kodemeio",
                "REDIS_URL": "redis://redis:6379",
                "DISPATCH_SECRET": "${DISPATCH_SECRET}",
                "JWT_SECRET": "${JWT_SECRET}",
                "ALLOWED_ORIGINS": allowed_origins,
                "FIREBASE_SERVICE_ACCOUNT_JSON": "${FIREBASE_SERVICE_ACCOUNT_JSON}",
            },
        }
    )

    env_example = (
        f"# Notify service for {name}\n"
        f"NODE_ENV=production\n"
        f"PORT=3020\n"
        f"DATABASE_URL=postgresql://kodemeio:CHANGE_ME@postgres:5432/kodemeio\n"
        f"REDIS_URL=redis://redis:6379\n"
        f"DISPATCH_SECRET=CHANGE_ME\n"
        f"JWT_SECRET=CHANGE_ME\n"
        f"ALLOWED_ORIGINS={allowed_origins}\n"
        f"FIREBASE_SERVICE_ACCOUNT_JSON=CHANGE_ME\n"
    )

    return yaml_filename, yaml_dump(instance), env_example_filename, env_example


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_tenant(tenant_path: Path) -> list[tuple[Path, str]]:
    """Generate all files for a single tenant.

    Returns list of (file_path, content) tuples.
    """
    raw = load_tenant(tenant_path)
    t = raw["tenant"]
    code = t["code"]

    # Stash odoo entries for notify generator
    t["_odoo_entries"] = raw.get("odoo", [])

    header = HEADER.format(code=code)
    files: list[tuple[Path, str]] = []

    environments = raw.get(
        "environments",
        {
            "production": {"server": "", "dns_suffix": "", "db_suffix": ""},
        },
    )

    for env_name, env_config in environments.items():
        server = env_config.get("server", "")
        dns_suffix = env_config.get("dns_suffix", "")
        db_suffix = env_config.get("db_suffix", "")
        inst_dir = INSTANCES_DIR / env_name
        env_dir = ENV_DIR / env_name

        # --- React PWAs + Odoo instances ---
        for odoo_entry in raw.get("odoo", []):
            # Odoo instance
            y_name, y_content, e_name, e_content = gen_odoo(
                t, odoo_entry, env_name, server, dns_suffix, db_suffix
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

            # React PWAs for this Odoo
            for app in odoo_entry.get("apps", []):
                y_name, y_content, e_name, e_content = gen_react_pwa(
                    t, odoo_entry, app, env_name, server, dns_suffix, db_suffix
                )
                files.append((inst_dir / y_name, header + y_content))
                files.append((env_dir / e_name, e_content))

        # --- Next.js corporate ---
        web = raw.get("web", {})
        if "corporate" in web:
            t["_web_corporate_brand"] = web["corporate"]["compose_brand"]
            y_name, y_content, e_name, e_content = gen_nextjs_corporate(
                t, env_name, server, dns_suffix
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # --- Next.js careers ---
        if web.get("careers"):
            y_name, y_content, e_name, e_content = gen_nextjs_careers(
                t, env_name, server, dns_suffix
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # --- Accurate-sync ---
        accurate_cfg = raw.get("accurate_sync")
        if accurate_cfg and accurate_cfg.get("enabled"):
            ref_short = accurate_cfg["odoo_ref"]
            try:
                odoo_entry = next(
                    e for e in raw.get("odoo", []) if e["short"] == ref_short
                )
            except StopIteration:
                raise ValueError(
                    f"accurate_sync.odoo_ref={ref_short!r} does not match any odoo[] entry in tenants/{code}.yaml"
                )
            acc_server = accurate_cfg.get("server", server)
            y_name, y_content, e_name, e_content = gen_accurate_sync(
                t, accurate_cfg, odoo_entry, env_name, acc_server, dns_suffix, db_suffix
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # --- Ofelia schedulers ---
        for scheduler in raw.get("schedulers", []):
            sched_server = scheduler.get("server", server)
            y_name, y_content, e_name, e_content = gen_ofelia(
                t, scheduler, env_name, sched_server
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # --- Notify ---
        services = raw.get("services", {})
        notify_cfg = services.get("notify")
        if notify_cfg:
            # `services.notify` accepts either `true` (use tenant default server)
            # or a mapping like `{server: tpp-prod-01}` to pin notify to a
            # specific host (e.g., colocate with tpp-infra-* services).
            notify_server = server
            if isinstance(notify_cfg, dict):
                notify_server = notify_cfg.get("server", server)
            y_name, y_content, e_name, e_content = gen_notify(
                t, env_name, notify_server, dns_suffix
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

    return files


def is_secret_env(path: Path) -> bool:
    """Check if a .env file likely contains secrets that must not be overwritten (Odoo, Notify, React PWA with OIDC).

    Note: .env.*-accurate-sync is intentionally NOT treated as secret — its
    contents are fully managed by the generator, which pulls PGPASSWORD and
    ODOO_ADMIN_PASSWD from the sibling .env.{tenant}-odoo-{short} file on
    every run. This keeps the accurate-sync env in lock-step with the Odoo
    instance it targets (no drift, no manual resync).
    """
    name = path.name
    return name.startswith(".env.") and (
        "-odoo-" in name or "-hono-notify" in name or "-react-" in name
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deploy instances from tenant manifests"
    )
    parser.add_argument(
        "--tenant", "-t", help="Generate for a single tenant (e.g., mac)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Preview without writing"
    )
    parser.add_argument(
        "--diff", "-d", action="store_true", help="Show diff vs existing files"
    )
    args = parser.parse_args()

    if args.tenant:
        tenant_files = [TENANTS_DIR / f"{args.tenant}.yaml"]
        if not tenant_files[0].exists():
            print(f"Error: tenant file not found: {tenant_files[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        tenant_files = sorted(TENANTS_DIR.glob("*.yaml"))
        if not tenant_files:
            print("No tenant files found in tenants/", file=sys.stderr)
            sys.exit(1)

    all_files: list[tuple[Path, str]] = []
    for tf in tenant_files:
        print(f"Processing tenant: {tf.stem}")
        all_files.extend(generate_tenant(tf))

    wrote = 0
    skipped = 0
    unchanged = 0

    for path, content in all_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        is_example = path.name.endswith(".example")
        existing_secret_env = not is_example and is_secret_env(path) and path.exists()

        if existing_secret_env:
            # Never overwrite .env files with secrets
            example_path = Path(str(path) + ".example")
            if args.diff and example_path.exists():
                old = example_path.read_text().splitlines(keepends=True)
                new = content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old, new, fromfile=str(example_path), tofile=str(example_path)
                )
                sys.stdout.writelines(diff)
            if not args.dry_run:
                example_path.write_text(content)
            print(f"  SKIP (secrets): {path.name} → wrote .example instead")
            skipped += 1
            continue

        if path.exists():
            existing = path.read_text()
            if existing == content:
                unchanged += 1
                continue
            if args.diff:
                old = existing.splitlines(keepends=True)
                new = content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old, new, fromfile=str(path), tofile=str(path)
                )
                sys.stdout.writelines(diff)

        if args.dry_run:
            print(f"  WOULD WRITE: {path.relative_to(DEPLOY_DIR)}")
        else:
            path.write_text(content)
            print(f"  WROTE: {path.relative_to(DEPLOY_DIR)}")
        wrote += 1

    action = "Would write" if args.dry_run else "Wrote"
    print(
        f"\nDone. {action}: {wrote}, Skipped (secrets): {skipped}, Unchanged: {unchanged}"
    )


if __name__ == "__main__":
    main()
