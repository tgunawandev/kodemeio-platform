"""Provisioning chain commands: onboard, offboard, status."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.models.provision import ChainResult, StepStatus
from kctl_ak.provision.chain import ProvisionChain
from kctl_ak.provision.config import load_provision_config

app = typer.Typer(help="Cross-system user provisioning (Authentik + Mailcow + Odoo).")


def _resolve_config_path() -> Path:
    """Find provision-config.yaml — check env, cwd, then shared config dir."""
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
            "steps": [{"name": s.name, "status": s.status.value, "detail": s.detail} for s in result.steps],
        }
        print(_json.dumps(data, indent=2))
        return

    output = c.output
    status_icons = {
        StepStatus.SUCCESS: "[green]\u2705[/green]",
        StepStatus.SKIPPED: "[dim]\u23ed\ufe0f [/dim]",
        StepStatus.FAILED: "[red]\u274c[/red]",
    }
    for i, step in enumerate(result.steps, 1):
        icon = status_icons.get(step.status, "?")
        detail = f" ({step.detail})" if step.detail else ""
        output.text(f"  Step {i}/{len(result.steps)}  {step.name} ... {icon}{detail}")

    if result.success:
        output.success(f"{result.action.title()} complete for {result.email}")
    else:
        output.error(f"{result.action.title()} incomplete for {result.email}")


def _build_chain(ctx: typer.Context, dry_run: bool) -> ProvisionChain:
    """Build a ProvisionChain from context and config."""
    c: AppContext = ctx.obj
    config_path = _resolve_config_path()
    config = load_provision_config(config_path)

    # Odoo credentials from env: ODOO_<TARGET_SLUG>_DB, ODOO_<TARGET_SLUG>_KEY
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

    # Authentik
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

    # Mailcow
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

    # Odoo targets
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

        # Fetch all employees with email
        employees = hrms._execute_kw(
            "hr.employee",
            "search_read",
            [[["active", "in", [True, False]]]],
            {"fields": ["name", "work_email", "active"], "limit": 0},
        )

        # Fetch all Authentik users with this company's domain
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
        generate_webhook_code,
        build_automation_vals,
        find_existing_automation,
        create_automation,
        update_automation,
        delete_automation,
        resolve_model_id,
        resolve_field_id,
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

        # Setup or update
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
