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
    tenant: dict, odoo_entry: dict, app: str
) -> tuple[str, str, str, str | None]:
    """Generate react-pwa instance YAML + env content.

    Returns (yaml_filename, yaml_content, env_filename, env_content).
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    short = odoo_entry["short"]
    app_upper = app.upper()

    yaml_filename = f"{domain}-react-{app}.yaml"
    env_filename = f"{domain}-react-{app}.env"

    instance = {
        "kind": "instance",
        "extends": "../bases/react-pwa.yaml",
        "instance": {
            "name": f"react-{app}-{code}",
            "description": f"{display} — {app_upper} PWA",
        },
        "project": domain,
        "source_overrides": {
            "compose_path": f"compose/docker-compose.{app}.yml",
        },
        "dns": {
            "zone": domain,
            "name": f"{app}-{code}",
        },
        "domain": {
            "host": f"{app}-{code}.{domain}",
            "port": 80,
            "service": app,
            "https": True,
        },
        "env_file": f"../env/{env_filename}",
        "env_overrides": {
            f"VITE_{app_upper}_APP_NAME": f"{display} {app_upper}",
            f"VITE_{app_upper}_API_BASE_URL": f"https://odoo-{short}-{code}.{domain}/{app}/api",
            "VITE_AUTH_MODE": "native",
            f"VITE_{app_upper}_OIDC_CLIENT_ID": "",
            f"VITE_{app_upper}_OIDC_REDIRECT_URI": "",
        },
    }

    env_content = (
        f"VITE_{app_upper}_APP_NAME={display} {app_upper}\n"
        f"VITE_{app_upper}_API_BASE_URL=https://odoo-{short}-{code}.{domain}/{app}/api\n"
        f"VITE_AUTH_MODE=native\n"
        f"VITE_OIDC_AUTHORITY=\n"
        f"VITE_{app_upper}_OIDC_CLIENT_ID=\n"
        f"VITE_{app_upper}_OIDC_REDIRECT_URI=\n"
        f"VITE_{app_upper}_THEME={app}\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_odoo(tenant: dict, odoo_entry: dict) -> tuple[str, str, str, str]:
    """Generate odoo instance YAML + env.example content.

    Returns (yaml_filename, yaml_content, env_example_filename, env_example_content).
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    profile = odoo_entry["profile"]
    short = odoo_entry["short"]
    description = odoo_entry.get("description", profile)
    workers = odoo_entry.get("workers", 4)
    db_name = f"odoo_{short}_{code}"

    yaml_filename = f"{domain}-odoo-{short}.yaml"
    env_example_filename = f"{domain}-odoo-{short}.env.example"

    instance = {
        "kind": "instance",
        "extends": "../bases/odoo.yaml",
        "instance": {
            "name": f"odoo-{short}-{code}",
            "description": f"{display} — {description}",
        },
        "project": domain,
        "dns": {
            "zone": domain,
            "name": f"odoo-{short}-{code}",
        },
        "domain": {
            "host": f"odoo-{short}-{code}.{domain}",
            "port": 8069,
            "service": "odoo-web",
            "https": True,
            "cert": "letsencrypt",
        },
        "database": {
            "name": db_name,
            "user": "odoo",
        },
        "env_file": f"../env/{domain}-odoo-{short}.env",
        "env_overrides": {
            "COMPOSE_PROJECT_NAME": f"odoo-{short}-{code}",
            "TENANT": code,
            "PGDATABASE": db_name,
            "PGUSER": "odoo",
            "ODOO_DB_FILTER": f"^{db_name}$",
            "DOMAIN": f"odoo-{short}-{code}.{domain}",
            "ODOO_WORKERS": str(workers),
        },
        "post_deploy": {
            "odoo_profile": f"profile-{profile}",
        },
    }

    env_example = (
        f"# =============================================================================\n"
        f"# {display} {description} — Production Environment\n"
        f"# =============================================================================\n"
        f"# Instance: odoo-{short}-{code}.{domain}\n"
        f"# Profile:  {profile}\n"
        f"# =============================================================================\n"
        f"\n"
        f"# PROJECT IDENTIFICATION\n"
        f"COMPOSE_PROJECT_NAME=odoo-{short}-{code}\n"
        f"TENANT={code}\n"
        f"DOMAIN=odoo-{short}-{code}.{domain}\n"
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
        f"RUNNING_ENV=production\n"
        f"WITHOUT_DEMO=True\n"
        f"ODOO_HTTP_PORT=8069\n"
        f"ODOO_GEVENT_PORT=8072\n"
        f"ODOO_DATA_DIR=/var/lib/odoo\n"
        f"ODOO_LOG_LEVEL=warn\n"
        f"ODOO_SERVER_WIDE_MODULES=base,web,bus,bus_alt_connection,session_db,dbfilter_from_header\n"
        f"\n"
        f"# DEPLOY PROFILE\n"
        f"ODOO_DEPLOY_PROFILE={profile}\n"
        f"ODOO_RUN_UPDATE=false\n"
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


def gen_nextjs_corporate(tenant: dict) -> tuple[str, str, str, str]:
    """Generate Next.js corporate website instance YAML + env."""
    code = tenant["code"]
    name = tenant["name"]
    display = tenant.get("short_name", name)
    domain = tenant["domain"]
    compose_brand = tenant["_web_corporate_brand"]

    yaml_filename = f"{domain}-nextjs-web.yaml"
    env_filename = f"{domain}-nextjs-web.env"

    instance = {
        "kind": "instance",
        "extends": "../bases/nextjs.yaml",
        "instance": {
            "name": f"web-{code}",
            "description": f"{name} company website",
        },
        "source_overrides": {
            "compose_path": f"compose/docker-compose.{compose_brand}.yml",
        },
        "project": domain,
        "dns": {
            "zone": domain,
            "name": "@",
        },
        "domain": {
            "host": domain,
            "port": 3000,
            "service": f"{compose_brand}-web",
            "https": True,
            "cert": "letsencrypt",
        },
        "env_file": f"../env/{env_filename}",
    }

    env_content = (
        f"NODE_ENV=production\nNEXT_PUBLIC_SITE_URL=https://{domain}\nTZ=Asia/Jakarta\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_nextjs_careers(tenant: dict) -> tuple[str, str, str, str]:
    """Generate Next.js careers portal instance YAML + env."""
    code = tenant["code"]
    name = tenant["name"]
    domain = tenant["domain"]

    yaml_filename = f"{domain}-nextjs-careers.yaml"
    env_filename = f"{domain}-nextjs-careers.env"

    instance = {
        "kind": "instance",
        "extends": "../bases/nextjs.yaml",
        "instance": {
            "name": f"careers-{code}",
            "description": f"{name} — Careers Portal (recruitment)",
        },
        "source_overrides": {
            "compose_path": "compose/docker-compose.prod.careers.yml",
        },
        "project": domain,
        "healthcheck": {
            "port": 4002,
        },
        "dns": {
            "zone": domain,
            "name": f"careers-{code}",
        },
        "domain": {
            "host": f"careers-{code}.{domain}",
            "port": 4002,
            "service": "careers",
            "https": True,
        },
        "env_overrides": {
            "NEXT_PUBLIC_SITE_URL": f"https://careers-{code}.{domain}",
            "NEXT_PUBLIC_SITE_NAME": name,
            "NEXT_PUBLIC_COMPANY_WEBSITE": f"https://{domain}",
            "NEXT_PUBLIC_API_URL": f"https://odoo-hrms-{code}.{domain}",
            "NEXT_PUBLIC_RECRUITMENT_API_URL": f"https://odoo-hrms-{code}.{domain}/recruitment/api",
            "API_URL": f"https://odoo-hrms-{code}.{domain}",
        },
    }

    env_content = (
        f"NODE_ENV=production\n"
        f"NEXT_PUBLIC_SITE_URL=https://careers-{code}.{domain}\n"
        f"NEXT_PUBLIC_SITE_NAME={name}\n"
        f"NEXT_PUBLIC_COMPANY_WEBSITE=https://{domain}\n"
        f"NEXT_PUBLIC_API_URL=https://odoo-hrms-{code}.{domain}\n"
        f"NEXT_PUBLIC_RECRUITMENT_API_URL=https://odoo-hrms-{code}.{domain}/recruitment/api\n"
        f"API_URL=https://odoo-hrms-{code}.{domain}\n"
        f"TZ=Asia/Jakarta\n"
    )

    return yaml_filename, yaml_dump(instance), env_filename, env_content


def gen_notify(tenant: dict) -> tuple[str, str, str, str]:
    """Generate notify service instance YAML + env.example."""
    code = tenant["code"]
    name = tenant["name"]
    domain = tenant["domain"]

    yaml_filename = f"{domain}-hono-notify.yaml"
    env_example_filename = f"{domain}-hono-notify.env.example"

    # Build ALLOWED_ORIGINS from all React PWA apps across all Odoo entries
    all_apps = []
    for odoo_entry in tenant.get("_odoo_entries", []):
        for app in odoo_entry.get("apps", []):
            all_apps.append(f"https://{app}-{code}.{domain}")
    allowed_origins = ",".join(all_apps)

    instance = {
        "kind": "instance",
        "extends": "../bases/infra.yaml",
        "instance": {
            "name": f"notify-{code}",
            "description": "Notification dispatch service (FCM push + SSE real-time + Telegram)",
        },
        "source_overrides": {
            "type": "github",
            "owner": "tgunawandev",
            "repo": "kodemeio-react",
            "branch": "main",
            "compose_path": "apps/api/notify/docker-compose.yml",
        },
        "server": "kodeme-service",
        "project": domain,
        "healthcheck": {
            "path": "/health",
            "port": 3020,
            "expected_status": 200,
            "timeout": 60,
            "interval": 10,
        },
        "dns": {
            "zone": domain,
            "name": f"notify-{code}",
        },
        "domain": {
            "host": f"notify-{code}.{domain}",
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
        "backup": {
            "enabled": False,
        },
    }

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
    domain = t["domain"]

    # Stash odoo entries for notify generator
    t["_odoo_entries"] = raw.get("odoo", [])

    header = HEADER.format(code=code)
    files: list[tuple[Path, str]] = []

    # --- React PWAs + Odoo instances ---
    for odoo_entry in raw.get("odoo", []):
        # Odoo instance
        y_name, y_content, e_name, e_content = gen_odoo(t, odoo_entry)
        files.append((INSTANCES_DIR / y_name, header + y_content))
        files.append((ENV_DIR / e_name, e_content))

        # React PWAs for this Odoo
        for app in odoo_entry.get("apps", []):
            y_name, y_content, e_name, e_content = gen_react_pwa(t, odoo_entry, app)
            files.append((INSTANCES_DIR / y_name, header + y_content))
            files.append((ENV_DIR / e_name, e_content))

    # --- Next.js corporate ---
    web = raw.get("web", {})
    if "corporate" in web:
        t["_web_corporate_brand"] = web["corporate"]["compose_brand"]
        y_name, y_content, e_name, e_content = gen_nextjs_corporate(t)
        files.append((INSTANCES_DIR / y_name, header + y_content))
        files.append((ENV_DIR / e_name, e_content))

    # --- Next.js careers ---
    if web.get("careers"):
        y_name, y_content, e_name, e_content = gen_nextjs_careers(t)
        files.append((INSTANCES_DIR / y_name, header + y_content))
        files.append((ENV_DIR / e_name, e_content))

    # --- Notify ---
    services = raw.get("services", {})
    if services.get("notify"):
        y_name, y_content, e_name, e_content = gen_notify(t)
        files.append((INSTANCES_DIR / y_name, header + y_content))
        files.append((ENV_DIR / e_name, e_content))

    return files


def is_secret_env(path: Path) -> bool:
    """Check if a .env file likely contains secrets (Odoo, Notify)."""
    name = path.name
    return (
        "-odoo-" in name
        and name.endswith(".env")
        or "-hono-notify" in name
        and name.endswith(".env")
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
        is_example = path.name.endswith(".env.example")
        existing_secret_env = not is_example and is_secret_env(path) and path.exists()

        if existing_secret_env:
            # Never overwrite .env files with secrets
            example_path = path.with_suffix(".env.example")
            if args.diff and example_path.exists():
                old = example_path.read_text().splitlines(keepends=True)
                new = content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old, new, fromfile=str(example_path), tofile=str(example_path)
                )
                sys.stdout.writelines(diff)
            if not args.dry_run:
                example_path.write_text(content)
            print(f"  SKIP (secrets): {path.name} → wrote .env.example instead")
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
