# MAC Staging Clone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy `stg-mac-odoo-erp.idtpp.com` and `stg-mac-odoo-hrms.idtpp.com` as clones of production MAC Odoo instances on the existing `tpp-prod-02` server, with production safety neutralization.

**Architecture:** Clone databases via pg_dump/pg_restore, reuse `tpp-prod-02` as the compose host (no new server), add production-safety neutralization step that disables outgoing mail/payment/webhook integrations in staging. Reuse the existing `deploys/instances/staging/mac-odoo-*.yaml` config files unchanged.

**Tech Stack:**
- `kctl-pg` — PostgreSQL operations (dump, restore, create, drop)
- `kctl-dokploy` — Dokploy compose service management
- `kctl-cf` — Cloudflare DNS
- `kctl-odoo` — Odoo administration + new `neutralize-staging` command
- Bash shell scripts — orchestration (`refresh-mac-staging.sh`)
- Python (Typer + httpx) — new kctl-odoo command

**Spec:** `docs/superpowers/specs/2026-04-10-mac-staging-clone-design.md`

---

## Prerequisites

- [ ] **Step 0.1: Verify SSH key exists for Hetzner servers**

Run:
```bash
ls -la ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
```
Expected: both files exist with mode `600`/`644`. If missing, copy from 1Password:
```bash
kctl-op read "op://kodemeio/hetzner-ssh-key/private-key" > ~/.ssh/id_ed25519
kctl-op read "op://kodemeio/hetzner-ssh-key/public-key" > ~/.ssh/id_ed25519.pub
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

- [ ] **Step 0.2: Verify kctl-pg can reach the PostgreSQL server**

Run:
```bash
kctl-pg db list 2>&1 | grep mac_odoo
```
Expected: both `mac_odoo_erp` and `mac_odoo_hrms` listed.

- [ ] **Step 0.3: Verify kctl-dokploy access**

Run:
```bash
kctl-dokploy compose list 2>&1 | grep mac-odoo
```
Expected: `mac-odoo-erp` and `mac-odoo-hrms` entries with status `done`.

- [ ] **Step 0.4: Verify kctl-cf access**

Run:
```bash
kctl-cf dns list --zone idtpp.com 2>&1 | grep mac-odoo-erp
```
Expected: A record for `mac-odoo-erp.idtpp.com` pointing to `46.224.93.123`.

---

## Task 1: Add `neutralize-staging` command to kctl-odoo

**Files:**
- Create: `cli-odoo/src/kctl_odoo/commands/staging.py`
- Modify: `cli-odoo/src/kctl_odoo/main.py` (register the new command group)
- Test: `cli-odoo/tests/test_staging.py`

- [ ] **Step 1.1: Write the failing test**

Create `cli-odoo/tests/test_staging.py`:
```python
"""Tests for the staging neutralization command."""
from unittest.mock import MagicMock

import pytest

from kctl_odoo.commands.staging import _neutralize_logic


def test_neutralize_disables_mail_servers():
    """All active mail servers should be deactivated."""
    client = MagicMock()
    client.search.side_effect = [
        [1, 2, 3],  # ir.mail_server ids
        [],  # payment.provider ids (none enabled)
        [],  # base.webhook ids (module not installed)
        [1],  # res.company
        [1],  # res.users (admin)
    ]
    client.execute_kw.return_value = True

    result = _neutralize_logic(
        client,
        base_url="https://stg-mac-odoo-erp.idtpp.com",
        admin_password="stg_admin_pw",
        company_prefix="[STG] ",
        dry_run=False,
    )

    # Should call write on ir.mail_server with active=False
    mail_server_call = [
        call for call in client.execute_kw.call_args_list
        if call.args[1] == "ir.mail_server" and call.args[2] == "write"
    ]
    assert len(mail_server_call) == 1
    assert mail_server_call[0].args[3] == [[1, 2, 3], {"active": False}]
    assert result["mail_servers_disabled"] == 3


def test_neutralize_dry_run_does_not_write():
    """Dry run should only read, not modify."""
    client = MagicMock()
    client.search.side_effect = [[1, 2], [], [], [1], [1]]

    _neutralize_logic(
        client,
        base_url="https://stg.example.com",
        admin_password="pw",
        company_prefix="[STG] ",
        dry_run=True,
    )

    # No write calls should be made
    write_calls = [
        call for call in client.execute_kw.call_args_list
        if call.args[2] == "write"
    ]
    assert len(write_calls) == 0


def test_neutralize_is_idempotent():
    """Running twice should work without errors (no mail servers to disable)."""
    client = MagicMock()
    # Second run: everything already disabled
    client.search.side_effect = [[], [], [], [1], [1]]

    result = _neutralize_logic(
        client,
        base_url="https://stg.example.com",
        admin_password="pw",
        company_prefix="[STG] ",
        dry_run=False,
    )

    assert result["mail_servers_disabled"] == 0
    assert result["payment_providers_disabled"] == 0
```

- [ ] **Step 1.2: Run test to verify it fails**

Run:
```bash
cd ~/code/kodemeio-odoo/cli-odoo
uv run pytest tests/test_staging.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kctl_odoo.commands.staging'`

- [ ] **Step 1.3: Create the staging command module**

Create `cli-odoo/src/kctl_odoo/commands/staging.py`:
```python
"""Staging environment management — neutralize production-like instances."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.client import OdooClient

app = typer.Typer(help="Staging environment operations")
console = Console()


def _neutralize_logic(
    client: OdooClient,
    base_url: str,
    admin_password: str,
    company_prefix: str,
    dry_run: bool,
) -> dict:
    """Neutralize a staging Odoo instance — idempotent, testable."""
    results = {
        "mail_servers_disabled": 0,
        "payment_providers_disabled": 0,
        "webhooks_disabled": 0,
        "companies_renamed": 0,
        "admin_password_set": False,
    }

    # 1. Disable all active outgoing mail servers
    mail_server_ids = client.search("ir.mail_server", [("active", "=", True)])
    if mail_server_ids:
        if not dry_run:
            client.execute_kw(
                "ir.mail_server", "write",
                [mail_server_ids, {"active": False}],
            )
        results["mail_servers_disabled"] = len(mail_server_ids)

    # 2. Disable payment providers
    provider_ids = client.search("payment.provider", [("state", "=", "enabled")])
    if provider_ids:
        if not dry_run:
            client.execute_kw(
                "payment.provider", "write",
                [provider_ids, {"state": "disabled"}],
            )
        results["payment_providers_disabled"] = len(provider_ids)

    # 3. Disable webhook endpoints (if base_webhook is installed)
    try:
        webhook_ids = client.search("webhook.endpoint", [("active", "=", True)])
        if webhook_ids and not dry_run:
            client.execute_kw(
                "webhook.endpoint", "write",
                [webhook_ids, {"active": False}],
            )
        results["webhooks_disabled"] = len(webhook_ids)
    except Exception:
        # base_webhook not installed — skip
        results["webhooks_disabled"] = 0

    # 4. Prefix company name with [STG]
    company_ids = client.search("res.company", [])
    if company_ids and not dry_run:
        for cid in company_ids:
            current = client.read("res.company", [cid], ["name"])[0]["name"]
            if not current.startswith(company_prefix):
                client.execute_kw(
                    "res.company", "write",
                    [[cid], {"name": f"{company_prefix}{current}"}],
                )
                results["companies_renamed"] += 1

    # 5. Set admin password
    admin_ids = client.search("res.users", [("login", "=", "admin")])
    if admin_ids and not dry_run:
        client.execute_kw(
            "res.users", "write",
            [admin_ids, {"password": admin_password}],
        )
        results["admin_password_set"] = True

    # 6. Update web.base.url system parameter
    if not dry_run:
        param_ids = client.search(
            "ir.config_parameter",
            [("key", "=", "web.base.url")],
        )
        if param_ids:
            client.execute_kw(
                "ir.config_parameter", "write",
                [param_ids, {"value": base_url}],
            )
        else:
            client.execute_kw(
                "ir.config_parameter", "create",
                [{"key": "web.base.url", "value": base_url}],
            )

    return results


@app.command("neutralize-staging")
def neutralize_staging(
    admin_password: str = typer.Option(
        ..., "--admin-password", envvar="STG_ADMIN_PASSWORD",
        help="New admin password for the staging instance",
    ),
    company_prefix: str = typer.Option(
        "[STG] ", "--company-prefix",
        help="Prefix to prepend to company names",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would be changed without modifying anything",
    ),
):
    """Neutralize a staging Odoo instance.

    Idempotent operation that:
    - Deactivates all ir.mail_server records (no real emails)
    - Disables all payment.provider records (no real charges)
    - Disables webhook.endpoint records (no outbound webhooks)
    - Prefixes company name with [STG]
    - Sets admin password
    - Updates web.base.url to match the current profile URL
    """
    from kctl_odoo.core.config import get_active_profile

    profile = get_active_profile()
    if "stg" not in profile.database.lower() and "staging" not in profile.database.lower():
        console.print(
            f"[red]REFUSED: profile database '{profile.database}' does not look "
            f"like a staging database. This command must only run on staging.[/red]"
        )
        raise typer.Exit(1)

    client = OdooClient.from_profile(profile)
    base_url = profile.url

    console.print(f"Neutralizing staging instance: [cyan]{base_url}[/cyan]")
    if dry_run:
        console.print("[yellow]DRY RUN — no changes will be made[/yellow]")

    results = _neutralize_logic(
        client,
        base_url=base_url,
        admin_password=admin_password,
        company_prefix=company_prefix,
        dry_run=dry_run,
    )

    table = Table(title="Neutralization Results")
    table.add_column("Item")
    table.add_column("Count", justify="right")
    for key, value in results.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)
```

- [ ] **Step 1.4: Register the command group in main.py**

Modify `cli-odoo/src/kctl_odoo/main.py`. Find the section where command groups are registered (look for `app.add_typer`) and add:

```python
from kctl_odoo.commands import staging
app.add_typer(staging.app, name="staging", help="Staging environment operations")
```

- [ ] **Step 1.5: Run test to verify it passes**

Run:
```bash
cd ~/code/kodemeio-odoo/cli-odoo
uv run pytest tests/test_staging.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 1.6: Verify command is registered**

Run:
```bash
uv run kctl-odoo staging --help
```
Expected: shows `neutralize-staging` subcommand.

- [ ] **Step 1.7: Commit**

```bash
cd ~/code/kodemeio-odoo
git add cli-odoo/src/kctl_odoo/commands/staging.py cli-odoo/src/kctl_odoo/main.py cli-odoo/tests/test_staging.py
git commit -m "feat(cli-odoo): add staging neutralize-staging command

Adds idempotent command to neutralize staging Odoo instances after
cloning from production. Disables mail servers, payment providers,
webhooks, prefixes company name with [STG], sets admin password,
and updates web.base.url.

Refuses to run on databases that don't have 'stg' or 'staging' in
the name as a safety guard.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Backup production databases

**Files:**
- Create: `~/backups/mac-stg-clone/mac_odoo_erp_*.sql.gz`
- Create: `~/backups/mac-stg-clone/mac_odoo_hrms_*.sql.gz`

- [ ] **Step 2.1: Create backup directory**

Run:
```bash
mkdir -p ~/backups/mac-stg-clone
cd ~/backups/mac-stg-clone
```

- [ ] **Step 2.2: Dump `mac_odoo_erp`**

Run:
```bash
TS=$(date +%Y%m%d_%H%M%S)
kctl-pg backup dump mac_odoo_erp --output "mac_odoo_erp_${TS}.sql.gz"
```
Expected: file created, output shows "Dump completed". Verify:
```bash
ls -lh mac_odoo_erp_${TS}.sql.gz
```
Expected: file size > 0 bytes (should be ~1-3 MB given 7MB DB size with gzip).

- [ ] **Step 2.3: Dump `mac_odoo_hrms`**

Run:
```bash
kctl-pg backup dump mac_odoo_hrms --output "mac_odoo_hrms_${TS}.sql.gz"
```
Expected: file created.
```bash
ls -lh mac_odoo_hrms_${TS}.sql.gz
```
Expected: file size > 0 bytes.

- [ ] **Step 2.4: Record the backup timestamp for later tasks**

Run:
```bash
echo "$TS" > ~/backups/mac-stg-clone/LATEST_TS
cat ~/backups/mac-stg-clone/LATEST_TS
```
Expected: timestamp string echoed.

---

## Task 3: Create staging env files from templates

**Files:**
- Create: `deploys/env/staging/.env.mac-odoo-erp`
- Create: `deploys/env/staging/.env.mac-odoo-hrms`

- [ ] **Step 3.1: Copy example files**

Run:
```bash
cd ~/code/kodemeio-platform/deploys/env/staging
cp .env.mac-odoo-erp.example .env.mac-odoo-erp
cp .env.mac-odoo-hrms.example .env.mac-odoo-hrms
```

- [ ] **Step 3.2: Retrieve secrets from 1Password**

Run:
```bash
PG_PASS=$(kctl-op read "op://kodemeio/mac-odoo/postgres-password")
ADMIN_PASS_STG=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
SMTP_PASS=$(kctl-op read "op://kodemeio/mac-odoo/smtp-password")
echo "Secrets retrieved: PG=${PG_PASS:0:4}*** ADMIN=${ADMIN_PASS_STG:0:4}*** SMTP=${SMTP_PASS:0:4}***"
```
Expected: three masked prefixes printed. If `staging-admin-password` doesn't exist in 1Password, create it first:
```bash
kctl-op create "op://kodemeio/mac-odoo/staging-admin-password" --generate
```

- [ ] **Step 3.3: Replace placeholders in `.env.mac-odoo-erp`**

Run:
```bash
cd ~/code/kodemeio-platform/deploys/env/staging
sed -i "s|PGPASSWORD=CHANGE_ME|PGPASSWORD=${PG_PASS}|" .env.mac-odoo-erp
sed -i "s|ODOO_ADMIN_PASSWD=CHANGE_ME|ODOO_ADMIN_PASSWD=${ADMIN_PASS_STG}|" .env.mac-odoo-erp
sed -i "s|SMTP_PASSWORD=CHANGE_ME|SMTP_PASSWORD=${SMTP_PASS}|" .env.mac-odoo-erp
```

Verify no `CHANGE_ME` remains:
```bash
grep CHANGE_ME .env.mac-odoo-erp || echo "No placeholders remaining"
```
Expected: "No placeholders remaining".

- [ ] **Step 3.4: Replace placeholders in `.env.mac-odoo-hrms`**

Run:
```bash
sed -i "s|PGPASSWORD=CHANGE_ME|PGPASSWORD=${PG_PASS}|" .env.mac-odoo-hrms
sed -i "s|ODOO_ADMIN_PASSWD=CHANGE_ME|ODOO_ADMIN_PASSWD=${ADMIN_PASS_STG}|" .env.mac-odoo-hrms
sed -i "s|SMTP_PASSWORD=CHANGE_ME|SMTP_PASSWORD=${SMTP_PASS}|" .env.mac-odoo-hrms
```
Verify:
```bash
grep CHANGE_ME .env.mac-odoo-hrms || echo "No placeholders remaining"
```
Expected: "No placeholders remaining".

- [ ] **Step 3.5: Disable auto init-db to prevent double-init**

Since we're restoring from production dumps, Odoo should NOT try to initialize the database on first boot. Run:
```bash
sed -i "s|ODOO_INIT_DB=true|ODOO_INIT_DB=false|" .env.mac-odoo-erp
sed -i "s|ODOO_INIT_DB=true|ODOO_INIT_DB=false|" .env.mac-odoo-hrms
```

- [ ] **Step 3.6: Add SENTRY_DSN=empty (don't send staging errors to GlitchTip)**

Run:
```bash
echo "" >> .env.mac-odoo-erp
echo "SENTRY_DSN=" >> .env.mac-odoo-erp
echo "" >> .env.mac-odoo-hrms
echo "SENTRY_DSN=" >> .env.mac-odoo-hrms
```

- [ ] **Step 3.7: Verify staging env files are git-ignored**

Run:
```bash
cd ~/code/kodemeio-platform
git status deploys/env/staging/
```
Expected: `.env.mac-odoo-erp` and `.env.mac-odoo-hrms` do NOT appear as untracked. If they do, check `.gitignore`:
```bash
grep "env/staging" .gitignore
```
Expected: pattern like `deploys/env/staging/.env.*` (excluding `.example`).

---

## Task 4: Create DNS records

**Files:** Cloudflare DNS zone `idtpp.com`

- [ ] **Step 4.1: Create A record for `stg-mac-odoo-erp`**

Run:
```bash
kctl-cf dns create \
  --zone idtpp.com \
  --name stg-mac-odoo-erp \
  --type A \
  --content 46.224.93.123 \
  --proxied
```
Expected: output confirms record created with proxy enabled.

- [ ] **Step 4.2: Create A record for `stg-mac-odoo-hrms`**

Run:
```bash
kctl-cf dns create \
  --zone idtpp.com \
  --name stg-mac-odoo-hrms \
  --type A \
  --content 46.224.93.123 \
  --proxied
```
Expected: record created.

- [ ] **Step 4.3: Verify DNS propagation**

Run:
```bash
sleep 1
dig +short stg-mac-odoo-erp.idtpp.com
dig +short stg-mac-odoo-hrms.idtpp.com
```
Expected: both resolve to Cloudflare proxy IPs (104.* or 172.*), not the origin IP.

---

## Task 5: Create staging databases

**Files:** PostgreSQL on `tpp-prod-01` (via kctl-pg SSH tunnel)

- [ ] **Step 5.1: Check if staging databases already exist**

Run:
```bash
kctl-pg db list 2>&1 | grep -E "stg_mac_odoo_(erp|hrms)"
```
If either exists, go to Step 5.2 to drop them. If neither exists, skip to Step 5.3.

- [ ] **Step 5.2: Drop existing staging databases (if any)**

Run (only if databases exist from Step 5.1):
```bash
kctl-pg db drop stg_mac_odoo_erp --force
kctl-pg db drop stg_mac_odoo_hrms --force
```
Expected: "Database dropped" messages.

- [ ] **Step 5.3: Create empty staging databases**

Run:
```bash
kctl-pg db create stg_mac_odoo_erp --owner odoo
kctl-pg db create stg_mac_odoo_hrms --owner odoo
```
Expected: "Database created" for both.

- [ ] **Step 5.4: Verify databases exist**

Run:
```bash
kctl-pg db list | grep stg_mac_odoo
```
Expected: both databases listed with owner `odoo` and small size (~7-8 MB initial).

---

## Task 6: Restore production dumps into staging databases

**Files:** Uses dumps from Task 2

- [ ] **Step 6.1: Restore `stg_mac_odoo_erp` from prod dump**

Run:
```bash
cd ~/backups/mac-stg-clone
TS=$(cat LATEST_TS)
kctl-pg backup restore stg_mac_odoo_erp "mac_odoo_erp_${TS}.sql.gz"
```
Expected: "Restore completed successfully".

- [ ] **Step 6.2: Restore `stg_mac_odoo_hrms` from prod dump**

Run:
```bash
kctl-pg backup restore stg_mac_odoo_hrms "mac_odoo_hrms_${TS}.sql.gz"
```
Expected: "Restore completed successfully".

- [ ] **Step 6.3: Verify restored databases have prod data**

Run:
```bash
kctl-pg query --database stg_mac_odoo_erp "SELECT count(*) FROM res_partner;"
kctl-pg query --database stg_mac_odoo_hrms "SELECT count(*) FROM hr_employee;"
```
Expected: both return non-zero counts matching prod.

Compare against prod:
```bash
kctl-pg query --database mac_odoo_erp "SELECT count(*) FROM res_partner;"
kctl-pg query --database mac_odoo_hrms "SELECT count(*) FROM hr_employee;"
```
Expected: counts match between prod and staging for each model.

- [ ] **Step 6.4: Pre-flight URL change at the database level**

Because Odoo reads `web.base.url` during startup, update it BEFORE first boot so links in the UI are correct from the start. Run:
```bash
kctl-pg query --database stg_mac_odoo_erp \
  "UPDATE ir_config_parameter SET value='https://stg-mac-odoo-erp.idtpp.com' WHERE key='web.base.url';"

kctl-pg query --database stg_mac_odoo_hrms \
  "UPDATE ir_config_parameter SET value='https://stg-mac-odoo-hrms.idtpp.com' WHERE key='web.base.url';"
```
Expected: "UPDATE 1" for each.

---

## Task 7: Create Dokploy compose services

**Files:**
- Existing: `deploys/instances/staging/mac-odoo-erp.yaml` (reused as-is)
- Existing: `deploys/instances/staging/mac-odoo-hrms.yaml` (reused as-is)

- [ ] **Step 7.1: Verify compose service does NOT already exist for staging**

Run:
```bash
kctl-dokploy compose list | grep -E "mac-odoo-(erp|hrms)-stg"
```
Expected: no matches. If matches exist, delete them first:
```bash
kctl-dokploy compose delete <id-of-existing-stg> --force
```

- [ ] **Step 7.2: Create `mac-odoo-erp-stg` compose service**

Run:
```bash
kctl-dokploy compose create \
  --project mac \
  --environment staging \
  --name mac-odoo-erp-stg \
  --source-type github \
  --repository tgunawandev/kodemeio-odoo \
  --branch main \
  --compose-path compose/odoo.prod.yml \
  --env-file ~/code/kodemeio-platform/deploys/env/staging/.env.mac-odoo-erp
```
Expected: "Compose service created" with an ID. Save the ID:
```bash
ERP_STG_ID=$(kctl-dokploy compose list | grep mac-odoo-erp-stg | awk '{print $2}')
echo $ERP_STG_ID
```

- [ ] **Step 7.3: Configure domain for `mac-odoo-erp-stg`**

Run:
```bash
kctl-dokploy compose domains add $ERP_STG_ID \
  --host stg-mac-odoo-erp.idtpp.com \
  --port 8069 \
  --service odoo-web \
  --https \
  --cert letsencrypt
```
Expected: domain added.

- [ ] **Step 7.4: Create `mac-odoo-hrms-stg` compose service**

Run:
```bash
kctl-dokploy compose create \
  --project mac \
  --environment staging \
  --name mac-odoo-hrms-stg \
  --source-type github \
  --repository tgunawandev/kodemeio-odoo \
  --branch main \
  --compose-path compose/odoo.prod.yml \
  --env-file ~/code/kodemeio-platform/deploys/env/staging/.env.mac-odoo-hrms

HRMS_STG_ID=$(kctl-dokploy compose list | grep mac-odoo-hrms-stg | awk '{print $2}')
echo $HRMS_STG_ID
```

- [ ] **Step 7.5: Configure domain for `mac-odoo-hrms-stg`**

Run:
```bash
kctl-dokploy compose domains add $HRMS_STG_ID \
  --host stg-mac-odoo-hrms.idtpp.com \
  --port 8069 \
  --service odoo-web \
  --https \
  --cert letsencrypt
```

- [ ] **Step 7.6: Start `mac-odoo-erp-stg`**

Run:
```bash
kctl-dokploy compose start $ERP_STG_ID
```
Expected: "Deploy started". Wait ~60 seconds for containers to start and Let's Encrypt to issue a cert:
```bash
sleep 60
kctl-dokploy compose logs $ERP_STG_ID --lines 50 | tail -20
```
Expected: Odoo logs showing successful startup, no errors.

- [ ] **Step 7.7: Start `mac-odoo-hrms-stg`**

Run:
```bash
kctl-dokploy compose start $HRMS_STG_ID
sleep 60
kctl-dokploy compose logs $HRMS_STG_ID --lines 50 | tail -20
```

- [ ] **Step 7.8: Smoke test HTTPS endpoints**

Run:
```bash
curl -I https://stg-mac-odoo-erp.idtpp.com/web/login
curl -I https://stg-mac-odoo-hrms.idtpp.com/web/login
```
Expected: both return HTTP 200 or 303 (redirect to login). HTTP 502/503/504 means the container isn't ready yet — wait 30 more seconds and retry.

---

## Task 8: Configure kctl-odoo staging profiles

**Files:** `~/.config/kodemeio/config.yaml`

- [ ] **Step 8.1: Retrieve the staging admin password from 1Password**

Run:
```bash
ADMIN_PASS_STG=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
```

- [ ] **Step 8.2: Create the `mac-erp-stg` profile**

Run:
```bash
kctl-odoo config quick mac-erp-stg \
  https://stg-mac-odoo-erp.idtpp.com \
  stg_mac_odoo_erp \
  "$ADMIN_PASS_STG" \
  --username admin
```
Expected: profile added.

- [ ] **Step 8.3: Create the `mac-hrms-stg` profile**

Run:
```bash
kctl-odoo config quick mac-hrms-stg \
  https://stg-mac-odoo-hrms.idtpp.com \
  stg_mac_odoo_hrms \
  "$ADMIN_PASS_STG" \
  --username admin
```

- [ ] **Step 8.4: Verify profiles work**

Run:
```bash
kctl-odoo -p mac-erp-stg doctor version-info
kctl-odoo -p mac-hrms-stg doctor version-info
```
Expected: both show Odoo 18.0, database names `stg_mac_odoo_erp` and `stg_mac_odoo_hrms`.

---

## Task 9: Run neutralization on both staging instances

**Files:** New command from Task 1

- [ ] **Step 9.1: Dry-run neutralization on ERP staging**

Run:
```bash
export STG_ADMIN_PASSWORD=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
kctl-odoo -p mac-erp-stg staging neutralize-staging --dry-run
```
Expected: table showing counts of items that would be disabled (mail servers, payment providers, etc.). No actual changes.

- [ ] **Step 9.2: Apply neutralization on ERP staging**

Run:
```bash
kctl-odoo -p mac-erp-stg staging neutralize-staging
```
Expected: table showing items disabled. Counts should be > 0 for mail servers and company renames.

- [ ] **Step 9.3: Verify neutralization on ERP staging**

Run:
```bash
kctl-odoo -p mac-erp-stg shell call ir.mail_server search_count '[[["active","=",true]]]'
# expected: 0

kctl-odoo -p mac-erp-stg shell call payment.provider search_count '[[["state","=","enabled"]]]'
# expected: 0

kctl-odoo -p mac-erp-stg shell call res.company search_read '[[],["name"]]'
# expected: name starts with [STG]
```

- [ ] **Step 9.4: Dry-run neutralization on HRMS staging**

Run:
```bash
kctl-odoo -p mac-hrms-stg staging neutralize-staging --dry-run
```

- [ ] **Step 9.5: Apply neutralization on HRMS staging**

Run:
```bash
kctl-odoo -p mac-hrms-stg staging neutralize-staging
```

- [ ] **Step 9.6: Verify neutralization on HRMS staging**

Run:
```bash
kctl-odoo -p mac-hrms-stg shell call ir.mail_server search_count '[[["active","=",true]]]'
kctl-odoo -p mac-hrms-stg shell call res.company search_read '[[],["name"]]'
```
Expected: mail servers 0, company name prefixed with `[STG]`.

- [ ] **Step 9.7: Idempotency check — run neutralization again**

Run:
```bash
kctl-odoo -p mac-erp-stg staging neutralize-staging
kctl-odoo -p mac-hrms-stg staging neutralize-staging
```
Expected: runs succeed, counts should be 0 (already disabled). No errors.

---

## Task 10: Create refresh-mac-staging.sh script

**Files:**
- Create: `scripts/refresh-mac-staging.sh`

- [ ] **Step 10.1: Create the refresh script**

Create `scripts/refresh-mac-staging.sh`:
```bash
#!/usr/bin/env bash
# Refresh MAC staging from production databases.
# Usage: ./scripts/refresh-mac-staging.sh
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${HOME}/backups/mac-stg-clone"
mkdir -p "$BACKUP_DIR"

echo "==> [$(date +%H:%M:%S)] Dumping mac_odoo_erp..."
kctl-pg backup dump mac_odoo_erp --output "$BACKUP_DIR/mac_odoo_erp_${TS}.sql.gz"

echo "==> [$(date +%H:%M:%S)] Dumping mac_odoo_hrms..."
kctl-pg backup dump mac_odoo_hrms --output "$BACKUP_DIR/mac_odoo_hrms_${TS}.sql.gz"

echo "==> [$(date +%H:%M:%S)] Recreating stg_mac_odoo_erp..."
kctl-pg db drop stg_mac_odoo_erp --force || true
kctl-pg db create stg_mac_odoo_erp --owner odoo
kctl-pg backup restore stg_mac_odoo_erp "$BACKUP_DIR/mac_odoo_erp_${TS}.sql.gz"

echo "==> [$(date +%H:%M:%S)] Recreating stg_mac_odoo_hrms..."
kctl-pg db drop stg_mac_odoo_hrms --force || true
kctl-pg db create stg_mac_odoo_hrms --owner odoo
kctl-pg backup restore stg_mac_odoo_hrms "$BACKUP_DIR/mac_odoo_hrms_${TS}.sql.gz"

echo "==> [$(date +%H:%M:%S)] Pre-flight URL update..."
kctl-pg query --database stg_mac_odoo_erp \
  "UPDATE ir_config_parameter SET value='https://stg-mac-odoo-erp.idtpp.com' WHERE key='web.base.url';"
kctl-pg query --database stg_mac_odoo_hrms \
  "UPDATE ir_config_parameter SET value='https://stg-mac-odoo-hrms.idtpp.com' WHERE key='web.base.url';"

echo "==> [$(date +%H:%M:%S)] Restarting Odoo containers..."
kctl-dokploy compose redeploy mac-odoo-erp-stg
kctl-dokploy compose redeploy mac-odoo-hrms-stg

echo "==> [$(date +%H:%M:%S)] Waiting for containers to be ready..."
sleep 90

echo "==> [$(date +%H:%M:%S)] Neutralizing staging..."
export STG_ADMIN_PASSWORD=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
kctl-odoo -p mac-erp-stg staging neutralize-staging
kctl-odoo -p mac-hrms-stg staging neutralize-staging

echo "==> [$(date +%H:%M:%S)] Smoke testing endpoints..."
curl -fsS -I https://stg-mac-odoo-erp.idtpp.com/web/login > /dev/null && echo "    ERP OK"
curl -fsS -I https://stg-mac-odoo-hrms.idtpp.com/web/login > /dev/null && echo "    HRMS OK"

# Keep only the 5 most recent backup pairs
echo "==> [$(date +%H:%M:%S)] Cleaning old backups (keeping 5 most recent)..."
cd "$BACKUP_DIR"
ls -1t mac_odoo_erp_*.sql.gz 2>/dev/null | tail -n +6 | xargs -r rm
ls -1t mac_odoo_hrms_*.sql.gz 2>/dev/null | tail -n +6 | xargs -r rm

echo "==> Done in ${SECONDS}s"
```

- [ ] **Step 10.2: Make it executable**

Run:
```bash
cd ~/code/kodemeio-platform
chmod +x scripts/refresh-mac-staging.sh
```

- [ ] **Step 10.3: Lint the script with shellcheck**

Run:
```bash
shellcheck scripts/refresh-mac-staging.sh
```
Expected: no errors.

- [ ] **Step 10.4: Commit the script**

Run:
```bash
cd ~/code/kodemeio-platform
git add scripts/refresh-mac-staging.sh
git commit -m "feat(scripts): add refresh-mac-staging.sh

One-command refresh of MAC staging from production databases.
Dumps prod, drops and recreates staging DBs, restores from dumps,
updates web.base.url, redeploys compose services, runs neutralization,
and smoke-tests both endpoints. Keeps 5 most recent backup pairs.

Refs: docs/superpowers/specs/2026-04-10-mac-staging-clone-design.md

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: End-to-end validation

- [ ] **Step 11.1: Visual verification in browser**

Open in browser:
- `https://stg-mac-odoo-erp.idtpp.com`
- `https://stg-mac-odoo-hrms.idtpp.com`

Log in with the staging admin password. Verify:
- [ ] Page loads (HTTP 200, not 502/503)
- [ ] Company name shows `[STG] CV Mandiri Agro Cemerlang`
- [ ] Database dropdown (if visible) shows `stg_mac_odoo_erp` / `stg_mac_odoo_hrms`
- [ ] Employee list (HRMS) or product list (ERP) has production data

- [ ] **Step 11.2: Verify production is unchanged**

Run:
```bash
kctl-pg query --database mac_odoo_erp "SELECT count(*) FROM res_partner;"
kctl-pg query --database mac_odoo_hrms "SELECT count(*) FROM hr_employee;"
```
Expected: same counts as before (compare to Step 6.3).

- [ ] **Step 11.3: Verify no outbound email is possible from staging**

Run:
```bash
kctl-odoo -p mac-erp-stg shell call ir.mail_server search '[[["active","=",true]]]'
kctl-odoo -p mac-hrms-stg shell call ir.mail_server search '[[["active","=",true]]]'
```
Expected: `[]` (empty array) for both.

- [ ] **Step 11.4: Create a test invoice in staging to confirm it works**

Run:
```bash
kctl-odoo -p mac-erp-stg shell call account.move create '[{"move_type":"out_invoice","partner_id":1,"invoice_line_ids":[[0,0,{"name":"Test staging invoice","quantity":1,"price_unit":100000}]]}]'
```
Expected: returns a new move ID. Confirm in browser that the draft invoice is visible under Accounting → Customers → Invoices.

- [ ] **Step 11.5: Verify test invoice does NOT trigger email**

Check mail queue:
```bash
kctl-odoo -p mac-erp-stg shell call mail.mail search_count '[[["state","=","outgoing"]]]'
```
Expected: count from before this test — no new outgoing mails queued.

---

## Task 12: Documentation

**Files:**
- Modify: `docs/operations/mac-staging-runbook.md`

- [ ] **Step 12.1: Create staging runbook**

Create `docs/operations/mac-staging-runbook.md`:
```markdown
# MAC Staging Runbook

**Staging URLs:**
- ERP: https://stg-mac-odoo-erp.idtpp.com
- HRMS: https://stg-mac-odoo-hrms.idtpp.com

**Server:** tpp-prod-02 (reused, not dedicated)
**Databases:** stg_mac_odoo_erp, stg_mac_odoo_hrms (on tpp-prod-01 PostgreSQL)
**Dokploy compose services:** mac-odoo-erp-stg, mac-odoo-hrms-stg

## Refresh from production

Run the script — takes ~5 minutes end to end:

```bash
cd ~/code/kodemeio-platform
./scripts/refresh-mac-staging.sh
```

## Manual operations

### Check staging health
```bash
curl -I https://stg-mac-odoo-erp.idtpp.com/web/login
curl -I https://stg-mac-odoo-hrms.idtpp.com/web/login
```

### View logs
```bash
kctl-dokploy compose logs mac-odoo-erp-stg --lines 100
kctl-dokploy compose logs mac-odoo-hrms-stg --lines 100
```

### Restart staging
```bash
kctl-dokploy compose redeploy mac-odoo-erp-stg
kctl-dokploy compose redeploy mac-odoo-hrms-stg
```

### Re-apply neutralization
```bash
export STG_ADMIN_PASSWORD=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
kctl-odoo -p mac-erp-stg staging neutralize-staging
kctl-odoo -p mac-hrms-stg staging neutralize-staging
```

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| 502 Bad Gateway | Container not ready | Wait 60s, check logs |
| "Database does not exist" | Staging DB not restored | Re-run refresh script |
| Emails being sent | Neutralization not applied | Run neutralize-staging |
| Login fails | Wrong admin password | Retrieve from 1Password `op://kodemeio/mac-odoo/staging-admin-password` |
| Company name not showing [STG] | Neutralization not applied | Run neutralize-staging |

## Rollback

If staging is broken beyond repair:
```bash
kctl-dokploy compose stop mac-odoo-erp-stg
kctl-dokploy compose stop mac-odoo-hrms-stg
kctl-pg db drop stg_mac_odoo_erp --force
kctl-pg db drop stg_mac_odoo_hrms --force
# Then re-run ./scripts/refresh-mac-staging.sh
```

Production is never affected.
```

- [ ] **Step 12.2: Commit the runbook**

Run:
```bash
cd ~/code/kodemeio-platform
git add docs/operations/mac-staging-runbook.md
git commit -m "docs(ops): add MAC staging runbook

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Acceptance Checklist

Run through these to confirm the implementation is complete:

- [ ] `https://stg-mac-odoo-erp.idtpp.com/web/login` returns HTTP 200
- [ ] `https://stg-mac-odoo-hrms.idtpp.com/web/login` returns HTTP 200
- [ ] Company name in both shows `[STG]` prefix
- [ ] `ir.mail_server` active count = 0 in both staging DBs
- [ ] `payment.provider` enabled count = 0 in staging ERP
- [ ] Production databases (`mac_odoo_erp`, `mac_odoo_hrms`) have unchanged row counts
- [ ] `kctl-odoo staging neutralize-staging --help` shows the new command
- [ ] `kctl-odoo staging neutralize-staging` tests pass in `cli-odoo/tests/test_staging.py`
- [ ] `scripts/refresh-mac-staging.sh` is executable and passes `shellcheck`
- [ ] `docs/operations/mac-staging-runbook.md` exists and documents the refresh process
- [ ] `docs/superpowers/specs/2026-04-10-mac-staging-clone-design.md` committed to `kodemeio-platform` repo
