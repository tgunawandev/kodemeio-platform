"""Provisioning chain commands: onboard, offboard, status."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.models.provision import ChainResult, StepStatus
from kctl_ak.provision.chain import ProvisionChain
from kctl_ak.provision.config import load_provision_config

app = typer.Typer(help="Cross-system user provisioning (Authentik + Mailcow + Odoo).")


def _resolve_config_path() -> Path:
    """Find provision-config.yaml -- check env, cwd, then shared config dir."""
    env_path = os.getenv("PROVISION_CONFIG")
    if env_path:
        return Path(env_path)
    candidates = [
        Path.cwd() / "provision-config.yaml",
        Path.home() / ".config" / "kodemeio" / "provision-config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"provision-config.yaml not found. Checked: $PROVISION_CONFIG, {candidates[0]}, {candidates[1]}"
    )


def _print_result(c: AppContext, result: ChainResult) -> None:
    """Print chain result as formatted step list or JSON."""
    if c.json_mode:
        import json as _json

        data = {
            "email": result.email,
            "action": result.action,
            "success": result.success,
            "name": result.name,
            "company_code": result.company_code,
            "user_id": result.user_id,
            "recovery_link": result.recovery_link,
            "groups": result.groups,
            "mailbox_quota_gb": result.mailbox_quota_gb,
            "apps": result.apps,
            "steps": [{"name": s.name, "status": s.status.value, "detail": s.detail} for s in result.steps],
        }
        print(_json.dumps(data, indent=2))
        return

    output = c.output
    status_icons = {
        StepStatus.SUCCESS: "[green]OK[/green]",
        StepStatus.SKIPPED: "[dim]SKIP[/dim]",
        StepStatus.FAILED: "[red]FAIL[/red]",
    }
    for i, step in enumerate(result.steps, 1):
        icon = status_icons.get(step.status, "?")
        detail = f" ({step.detail})" if step.detail else ""
        output.text(f"  Step {i}/{len(result.steps)}  {step.name} ... {icon}{detail}")

    if result.success:
        output.success(f"{result.action.title()} complete for {result.email}")
    else:
        output.error(f"{result.action.title()} incomplete for {result.email}")


def _print_onboard_report(c: AppContext, result: ChainResult) -> None:
    """Print full onboarding report with email and WhatsApp templates."""
    output = c.output
    domain = result.email.split("@", 1)[1]
    sso_url = f"https://auth.{domain}"
    link = result.recovery_link or "[recovery link not available]"

    output.text("")
    output.header(f"Onboarding Report: {result.name}")

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    sections.append(
        (
            "Authentik (SSO)",
            [
                ("User ID", str(result.user_id or "N/A")),
                ("Username", result.email.split("@")[0]),
                ("Email", result.email),
                ("Groups", ", ".join(result.groups) if result.groups else "(none)"),
            ],
        )
    )
    sections.append(
        (
            "Mailcow (Email)",
            [
                ("Mailbox", result.email),
                ("Quota", f"{result.mailbox_quota_gb} GB" if result.mailbox_quota_gb else "N/A"),
                ("Auth Source", "generic-oidc"),
            ],
        )
    )
    if result.recovery_link:
        sections.append(
            (
                "Recovery Link",
                [("URL", result.recovery_link), ("Expiry", "7 days, one-time use")],
            )
        )
    output.detail(f"Systems provisioned for {result.email}", sections)

    apps_padded = "\n".join(f"  {label:<16}: {url}" for label, url in result.apps.items())
    apps_plain = "\n".join(f"- {label}: {url}" for label, url in result.apps.items())

    email_tpl = (
        f"Subject: Selamat Datang di {result.company_code}"
        f" - Akun Digital Anda Sudah Aktif\n\n"
        f"Yth. {result.name},\n\n"
        f"Selamat datang di {result.company_code}!"
        f" Akun digital Anda telah diaktifkan.\n\n"
        f"Email     : {result.email}\n"
        f"Login SSO : {sso_url}\n\n"
        f"Langkah pertama:\n"
        f"1. Buka link aktivasi berikut (berlaku 7 hari, sekali pakai):\n"
        f"   {link}\n"
        f"2. Buat password baru Anda\n"
        f"3. Setelah itu, login ke semua aplikasi {result.company_code}"
        f" menggunakan email & password di atas\n\n"
        f"Aplikasi yang bisa diakses:\n{apps_padded}\n\n"
        + (f"Panduan lengkap setup Desktop & Mobile:\n  {result.guide_url}\n\n" if result.guide_url else "")
        + f"Jika ada kendala, hubungi IT Support.\n\n"
        f"Salam,\nIT Department - {result.company_code}"
    )

    wa_tpl = (
        f"Halo {result.name},\n\n"
        f"Selamat datang di {result.company_code}!"
        f" Akun digital kamu sudah aktif:\n\n"
        f"Email: {result.email}\n"
        f"Login: {sso_url}\n\n"
        f"Langkah aktivasi:\n"
        f"1. Buka link ini (berlaku 7 hari): {link}\n"
        f"2. Buat password baru\n"
        f"3. Setelah itu bisa login ke semua aplikasi {result.company_code}"
        f" pakai email & password tsb\n\n"
        f"Aplikasi:\n{apps_plain}\n\n"
        + (f"Panduan setup Desktop & Mobile:\n{result.guide_url}\n\n" if result.guide_url else "")
        + f"Kalau ada masalah, hubungi IT ya."
    )

    output.text("\n[bold]--- Email Template ---[/bold]")
    output.text(email_tpl)
    output.text("\n[bold]--- WhatsApp Template ---[/bold]")
    output.text(wa_tpl)


def _save_onboard_log(result: ChainResult) -> Path | None:
    """Save onboarding report as markdown log file."""
    log_dir = (
        Path.home()
        / "project"
        / "00-new-projects"
        / "kodemeio-workspace"
        / "kodemeio-platform"
        / "onboarding-logs"
        / result.company_code.lower()
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    slug = result.email.split("@")[0].replace(".", "-")
    log_path = log_dir / f"{today}_{slug}.md"

    domain = result.email.split("@", 1)[1]
    sso_url = f"https://auth.{domain}"
    link = result.recovery_link or "[not available]"
    apps_email = "\n".join(f"  {label:<16}: {url}" for label, url in result.apps.items())
    apps_wa = "\n".join(f"- {label}: {url}" for label, url in result.apps.items())

    steps_table = "\n".join(
        f"| {s.name} | "
        f"{'OK' if s.status == StepStatus.SUCCESS else 'Skipped' if s.status == StepStatus.SKIPPED else 'FAILED'}"
        f" | {s.detail} |"
        for s in result.steps
    )

    content = f"""# Onboarding Report: {result.name}

- **Date**: {today}
- **Email**: {result.email}
- **Company**: {result.company_code}

## Provisioning Steps

| Step | Status | Detail |
|------|--------|--------|
{steps_table}

## Authentik (SSO)

| Item | Value |
|------|-------|
| User ID | {result.user_id or "N/A"} |
| Username | {result.email.split("@")[0]} |
| Email | {result.email} |
| Groups | {", ".join(result.groups) if result.groups else "(none)"} |

## Mailcow (Email)

| Item | Value |
|------|-------|
| Mailbox | {result.email} |
| Quota | {result.mailbox_quota_gb} GB |
| Auth Source | generic-oidc |

## Recovery Link

- URL: {link}
- Expiry: 7 days, one-time use

## Email Template

```
Subject: Selamat Datang di {result.company_code} - Akun Digital Anda Sudah Aktif

Yth. {result.name},

Selamat datang di {result.company_code}! Akun digital Anda telah diaktifkan.

Email     : {result.email}
Login SSO : {sso_url}

Langkah pertama:
1. Buka link aktivasi berikut (berlaku 7 hari, sekali pakai):
   {link}
2. Buat password baru Anda
3. Setelah itu, login ke semua aplikasi {result.company_code} menggunakan email & password di atas

Aplikasi yang bisa diakses:
{apps_email}
{
        ""
        if not result.guide_url
        else f'''
Panduan lengkap setup Desktop & Mobile:
  {result.guide_url}
'''
    }Jika ada kendala, hubungi IT Support.

Salam,
IT Department - {result.company_code}
```

## WhatsApp Template

```
Halo {result.name},

Selamat datang di {result.company_code}! Akun digital kamu sudah aktif:

Email: {result.email}
Login: {sso_url}

Langkah aktivasi:
1. Buka link ini (berlaku 7 hari): {link}
2. Buat password baru
3. Setelah itu bisa login ke semua aplikasi {result.company_code} pakai email & password tsb

Aplikasi:
{apps_wa}
{
        ""
        if not result.guide_url
        else f'''
Panduan setup Desktop & Mobile:
{result.guide_url}
'''
    }Kalau ada masalah, hubungi IT ya.
```
"""
    log_path.write_text(content)
    return log_path


def _build_chain(ctx: typer.Context, dry_run: bool) -> ProvisionChain:
    """Build a ProvisionChain from context and config."""
    c: AppContext = ctx.obj
    config_path = _resolve_config_path()
    config = load_provision_config(config_path)

    odoo_creds: dict[str, dict[str, str]] = {}
    for company_cfg in config.companies.values():
        for target in company_cfg.odoo_targets:
            slug = target.replace(".", "_").replace("-", "_").upper()
            db = os.getenv(f"ODOO_{slug}_DB", "")
            key = os.getenv(f"ODOO_{slug}_KEY", "")
            if db and key:
                odoo_creds[target] = {
                    "database": db,
                    "api_key": key,
                    "username": os.getenv(f"ODOO_{slug}_USER", "admin"),
                }

    return ProvisionChain(
        ak_client=c.client,
        config=config,
        output=c.output,
        mailcow_api_key=os.getenv("MAILCOW_API_KEY", ""),
        odoo_credentials=odoo_creds,
        dry_run=dry_run,
    )


@app.command()
def onboard(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Employee email (e.g., john.doe@mandiriagro.com)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Full name")] = "",
    company: Annotated[str | None, typer.Option("--company", "-c", help="Company code (mac/tpp/kod)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen")] = False,
) -> None:
    """Provision user across Authentik, Mailcow, and Odoo."""
    c: AppContext = ctx.obj
    if not name:
        name = email.split("@")[0].replace(".", " ").title()

    chain = _build_chain(ctx, dry_run)
    result = chain.onboard(email=email, name=name, company=company)
    _print_result(c, result)

    if result.success and not dry_run:
        _print_onboard_report(c, result)
        log_path = _save_onboard_log(result)
        if log_path:
            c.output.info(f"Log saved: {log_path}")

    if not result.success:
        raise typer.Exit(1)


@app.command()
def offboard(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Employee email to deactivate")],
    company: Annotated[str | None, typer.Option("--company", "-c", help="Company code (mac/tpp/kod)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen")] = False,
) -> None:
    """Disable user across Authentik, Mailcow, and Odoo."""
    c: AppContext = ctx.obj
    chain = _build_chain(ctx, dry_run)
    result = chain.offboard(email=email, company=company)
    _print_result(c, result)

    if not result.success:
        raise typer.Exit(1)


@app.command()
def status(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Employee email to check")],
) -> None:
    """Check user status across all systems."""
    c: AppContext = ctx.obj
    config_path = _resolve_config_path()
    config = load_provision_config(config_path)

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    ak_data = c.client.get("core/users/", params={"email": email})
    users = ak_data.get("results", [])
    if users:
        user = users[0]
        groups = [g["name"] for g in user.get("groups_obj", [])]
        active = "active" if user.get("is_active") else "inactive"
        sections.append(
            (
                "Authentik",
                [
                    ("Status", active),
                    ("User ID", str(user["pk"])),
                    ("Groups", ", ".join(groups) if groups else "(none)"),
                    ("Last Login", str(user.get("last_login", "never"))),
                ],
            )
        )
    else:
        sections.append(("Authentik", [("Status", "not found")]))

    mailcow_key = os.getenv("MAILCOW_API_KEY", "")
    if mailcow_key:
        from kctl_ak.provision.mailcow_client import MailcowProvisionClient

        mc = MailcowProvisionClient(api_url=config.mailcow.api_url, api_key=mailcow_key)
        mailbox = mc.get_mailbox(email)
        if mailbox:
            active = "active" if str(mailbox.get("active")) == "1" else "disabled"
            sections.append(
                (
                    "Mailcow",
                    [
                        ("Status", active),
                        ("Messages", str(mailbox.get("messages", 0))),
                    ],
                )
            )
        else:
            sections.append(("Mailcow", [("Status", "no mailbox")]))
    else:
        sections.append(("Mailcow", [("Status", "MAILCOW_API_KEY not set")]))

    domain = email.split("@", 1)[1]
    for code, cfg in config.companies.items():
        if cfg.domain != domain:
            continue
        for target in cfg.odoo_targets:
            slug = target.replace(".", "_").replace("-", "_").upper()
            db = os.getenv(f"ODOO_{slug}_DB", "")
            key = os.getenv(f"ODOO_{slug}_KEY", "")
            if db and key:
                from kctl_ak.provision.odoo_client import OdooProvisionClient

                odoo = OdooProvisionClient(
                    base_url=f"https://{target}",
                    database=db,
                    api_key=key,
                )
                user = odoo.get_user(email)
                if user:
                    active = "active" if user.get("active") else "inactive"
                    sections.append((f"Odoo {target}", [("Status", active), ("ID", str(user["id"]))]))
                else:
                    sections.append((f"Odoo {target}", [("Status", "not found")]))
            else:
                sections.append((f"Odoo {target}", [("Status", "no credentials")]))

    c.output.detail(f"Provision Status: {email}", sections)


@app.command()
def sync(
    ctx: typer.Context,
    company: Annotated[str | None, typer.Option("--company", "-c", help="Company code (mac/tpp/kod)")] = None,
    all_companies: Annotated[bool, typer.Option("--all", help="Sync all companies")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen")] = True,
) -> None:
    """Poll HRMS and reconcile users across systems."""
    c: AppContext = ctx.obj
    config_path = _resolve_config_path()
    config = load_provision_config(config_path)

    companies_to_sync: list[str] = []
    if all_companies:
        companies_to_sync = [code for code, cfg in config.companies.items() if cfg.hrms]
    elif company:
        if company not in config.companies:
            c.output.error(f"Unknown company: {company}")
            raise typer.Exit(1)
        if not config.companies[company].hrms:
            c.output.error(f"Company {company} has no HRMS configured")
            raise typer.Exit(1)
        companies_to_sync = [company]
    else:
        c.output.error("Specify --company or --all")
        raise typer.Exit(1)

    for code in companies_to_sync:
        cfg = config.companies[code]
        slug = cfg.hrms.replace(".", "_").replace("-", "_").upper() if cfg.hrms else ""
        db = os.getenv(f"ODOO_{slug}_DB", "")
        key = os.getenv(f"ODOO_{slug}_KEY", "")

        if not db or not key:
            c.output.warn(f"Skipping {code}: HRMS credentials not configured (need ODOO_{slug}_DB and ODOO_{slug}_KEY)")
            continue

        c.output.info(f"Syncing {code} from {cfg.hrms}...")

        from kctl_ak.provision.odoo_client import OdooProvisionClient

        hrms = OdooProvisionClient(base_url=f"https://{cfg.hrms}", database=db, api_key=key)

        employees = hrms._execute_kw(
            "hr.employee",
            "search_read",
            [[["active", "in", [True, False]]]],
            {"fields": ["name", "work_email", "active"], "limit": 0},
        )

        ak_users_data = c.client.get("core/users/", params={"search": f"@{cfg.domain}", "page_size": 500})
        ak_users = {
            u["email"]: u for u in ak_users_data.get("results", []) if u.get("email", "").endswith(f"@{cfg.domain}")
        }

        chain = _build_chain(ctx, dry_run)

        new_count = 0
        archive_count = 0
        skip_count = 0

        for emp in employees:
            email = emp.get("work_email", "")
            if not email or not email.endswith(f"@{cfg.domain}"):
                continue

            emp_active = emp.get("active", True)
            ak_user = ak_users.pop(email, None)

            if emp_active and not ak_user:
                c.output.info(f"  NEW: {email} ({emp.get('name', '')})")
                if not dry_run:
                    chain.onboard(email=email, name=emp.get("name", ""), company=code)
                new_count += 1
            elif not emp_active and ak_user and ak_user.get("is_active"):
                c.output.info(f"  ARCHIVE: {email}")
                if not dry_run:
                    chain.offboard(email=email)
                archive_count += 1
            else:
                skip_count += 1

        c.output.success(f"{code}: {new_count} new, {archive_count} archived, {skip_count} unchanged")


@app.command("setup-webhook")
def setup_webhook(
    ctx: typer.Context,
    company: Annotated[str | None, typer.Option("--company", "-c", help="Company code (mac/tpp/kod)")] = None,
    all_companies: Annotated[bool, typer.Option("--all", help="Setup for all companies with HRMS")] = False,
    check: Annotated[bool, typer.Option("--check", help="Check webhook status without changes")] = False,
    remove: Annotated[bool, typer.Option("--remove", help="Remove webhook automation")] = False,
    ak_sync_url: Annotated[
        str, typer.Option("--url", help="ak-sync webhook URL")
    ] = "https://ak-sync.kodeme.io/webhook/odoo-hrms",
) -> None:
    """Setup Odoo HRMS automated action to fire webhooks to ak-sync."""
    c: AppContext = ctx.obj
    config_path = _resolve_config_path()
    config = load_provision_config(config_path)

    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    hmac_key = os.getenv("ODOO_WEBHOOK_HMAC_KEY", "")

    if not check and not remove and (not webhook_secret or not hmac_key):
        c.output.error("WEBHOOK_SECRET and ODOO_WEBHOOK_HMAC_KEY env vars required")
        raise typer.Exit(1)

    companies_to_setup: list[str] = []
    if all_companies:
        companies_to_setup = [code for code, cfg in config.companies.items() if cfg.hrms]
    elif company:
        if company not in config.companies:
            c.output.error(f"Unknown company: {company}")
            raise typer.Exit(1)
        if not config.companies[company].hrms:
            c.output.error(f"Company {company} has no HRMS configured")
            raise typer.Exit(1)
        companies_to_setup = [company]
    else:
        c.output.error("Specify --company or --all")
        raise typer.Exit(1)

    from kctl_ak.provision.webhook_setup import (
        build_automation_vals,
        create_automation,
        delete_automation,
        find_existing_automation,
        generate_webhook_code,
        resolve_field_id,
        resolve_model_id,
        update_automation,
    )

    rows: list[list[str]] = []

    for code in companies_to_setup:
        cfg = config.companies[code]
        profile = f"{code}-hrms"

        if check:
            try:
                existing = find_existing_automation(profile)
                if existing:
                    active = "active" if existing.get("active") else "inactive"
                    has_url = ak_sync_url in (existing.get("code") or "")
                    status = f"configured ({active})" if has_url else f"configured ({active}, URL mismatch)"
                    rows.append([code.upper(), cfg.hrms or "", f"[green]{status}[/green]"])
                else:
                    rows.append([code.upper(), cfg.hrms or "", "[red]not configured[/red]"])
            except Exception as e:
                rows.append([code.upper(), cfg.hrms or "", f"[red]error: {e}[/red]"])
            continue

        if remove:
            try:
                existing = find_existing_automation(profile)
                if existing:
                    delete_automation(profile, existing["id"])
                    c.output.success(f"{code}: webhook automation removed")
                else:
                    c.output.info(f"{code}: no automation found, nothing to remove")
            except Exception as e:
                c.output.error(f"{code}: failed to remove: {e}")
            continue

        try:
            c.output.info(f"{code}: resolving model IDs on {cfg.hrms}...")
            model_id = resolve_model_id(profile, "hr.employee")
            field_id = resolve_field_id(profile, "hr.employee", "active")

            webhook_code = generate_webhook_code(
                webhook_url=ak_sync_url,
                webhook_secret=webhook_secret,
                hmac_key=hmac_key,
                company_code=code,
                hrms_domain=cfg.hrms or "",
            )

            vals = build_automation_vals(
                model_id=model_id,
                active_field_id=field_id,
                code=webhook_code,
            )

            existing = find_existing_automation(profile)
            if existing:
                update_automation(profile, existing["id"], vals)
                c.output.success(f"{code}: webhook automation updated (id: {existing['id']})")
            else:
                record_id = create_automation(profile, vals)
                c.output.success(f"{code}: webhook automation created (id: {record_id})")

        except Exception as e:
            c.output.error(f"{code}: setup failed: {e}")

    if check and rows:
        c.output.table(
            "Webhook Status",
            [("Company", "cyan"), ("HRMS Instance", ""), ("Status", "")],
            rows,
        )
