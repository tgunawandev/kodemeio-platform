"""Sequential provisioning chain: Authentik → Mailcow → Odoo."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from kctl_ak.core.client import AuthentikClient
from kctl_ak.models.provision import (
    ChainResult,
    CompanyConfig,
    ProvisionConfig,
    StepStatus,
)
from kctl_ak.provision.mailcow_client import MailcowProvisionClient
from kctl_ak.provision.odoo_client import OdooProvisionClient


def _send_telegram_notification(result: ChainResult) -> None:
    """Send provisioning result to Telegram admin chat (best-effort, never raises)."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    icon = "OK" if result.success else "FAIL"
    action = result.action.upper()
    steps_text = "\n".join(
        f"  {'[OK]' if s.status == StepStatus.SUCCESS else '[SKIP]' if s.status == StepStatus.SKIPPED else '[FAIL]'} {s.name}: {s.detail}"
        for s in result.steps
    )
    text = f"{icon} *{action}* `{result.email}`\n\n{steps_text}"

    try:
        httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass  # Best-effort, never fail the chain for a notification


class ProvisionChain:
    """Orchestrates user provisioning across Authentik, Mailcow, and Odoo."""

    MAX_RETRIES = 3
    BACKOFF_BASE = 1  # seconds

    def __init__(
        self,
        ak_client: AuthentikClient,
        config: ProvisionConfig,
        output: Any,
        mailcow_api_key: str = "",
        odoo_credentials: dict[str, dict[str, str]] | None = None,
        dry_run: bool = False,
    ) -> None:
        self.ak = ak_client
        self.config = config
        self.output = output
        self.mailcow_api_key = mailcow_api_key or os.getenv("MAILCOW_API_KEY", "")
        self.odoo_credentials = odoo_credentials or {}
        self.dry_run = dry_run

    def _company_config(self, email: str, company: str | None = None) -> tuple[str, CompanyConfig]:
        """Resolve company from email domain or explicit company code."""
        if company and company in self.config.companies:
            return company, self.config.companies[company]
        domain = email.split("@", 1)[1]
        for code, cfg in self.config.companies.items():
            if cfg.domain == domain:
                return code, cfg
        raise ValueError(f"No company config for domain: {domain}")

    def _retry(self, fn: Any, step_name: str, result: ChainResult) -> bool:
        """Retry a step with exponential backoff. Returns True on success."""
        for attempt in range(self.MAX_RETRIES):
            try:
                fn()
                return True
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.BACKOFF_BASE * (4**attempt)
                    self.output.warn(f"  {step_name} failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    result.add(step_name, StepStatus.FAILED, str(e))
                    return False
        return False

    # --- ONBOARD ---

    def onboard(self, email: str, name: str, company: str | None = None) -> ChainResult:
        """Provision user across all systems."""
        result = ChainResult(email=email, action="onboard", name=name)
        company_code, company_cfg = self._company_config(email, company)
        result.company_code = company_code.upper()
        result.apps = dict(company_cfg.apps)
        result.guide_url = company_cfg.guide_url

        self.output.header(f"Provisioning {email} ({company_code.upper()} - {company_cfg.domain})")

        # Step 1: Authentik
        user_id = self._step_ak_create(email, name, result)
        if user_id is None and not self.dry_run:
            return result
        result.user_id = user_id

        # Step 2: Group assignment
        if self.dry_run:
            groups = ", ".join(company_cfg.default_groups) if company_cfg.default_groups else "none"
            result.add("Authentik groups", StepStatus.SKIPPED, f"dry-run ({groups})")
        elif user_id:
            self._step_ak_groups(user_id, company_cfg, result)

        # Step 3: Mailcow
        self._step_mailcow_create(email, name, company_cfg, result)

        # Step 4: Odoo targets
        self._step_odoo_sync(email, name, company_code, company_cfg, result)

        # Step 5: Recovery link
        if self.dry_run:
            result.add("Recovery link", StepStatus.SKIPPED, "dry-run")
        elif user_id:
            self._step_recovery_link(user_id, result)

        # Notify admin via Telegram
        if not self.dry_run:
            _send_telegram_notification(result)

        return result

    def _step_ak_create(self, email: str, name: str, result: ChainResult) -> int | None:
        """Create or update Authentik user. Returns user pk."""
        step = "Authentik user"
        if self.dry_run:
            result.add(step, StepStatus.SKIPPED, "dry-run")
            return None

        # Check if exists
        existing = self.ak.get("core/users/", params={"email": email})
        users = existing.get("results", [])

        if users:
            user = users[0]
            pk = user["pk"]
            if not user.get("is_active"):
                self.ak.patch(f"core/users/{pk}/", data={"is_active": True})
                result.add(step, StepStatus.SUCCESS, f"reactivated (uid: {pk})")
            else:
                result.add(step, StepStatus.SKIPPED, f"already active (uid: {pk})")
            return pk

        username = email.split("@")[0]
        created = self.ak.post(
            "core/users/",
            data={
                "username": username,
                "email": email,
                "name": name,
                "is_active": True,
            },
        )
        pk = created["pk"]
        result.add(step, StepStatus.SUCCESS, f"created (uid: {pk})")
        return pk

    def _step_ak_groups(self, user_id: int, company_cfg: CompanyConfig, result: ChainResult) -> None:
        """Add user to default Authentik groups for this company."""
        step = "Authentik groups"
        if not company_cfg.default_groups:
            result.add(step, StepStatus.SKIPPED, "no default_groups configured")
            return

        added: list[str] = []
        already: list[str] = []
        failed: list[str] = []

        for group_name in company_cfg.default_groups:
            try:
                groups_resp = self.ak.get("core/groups/", params={"name": group_name})
                groups = groups_resp.get("results", [])
                if not groups:
                    failed.append(f"{group_name} (not found)")
                    continue

                group = groups[0]
                group_pk = group["pk"]
                current_users = group.get("users", [])

                if user_id in current_users:
                    already.append(group_name)
                    result.groups.append(group_name)
                else:
                    self.ak.post(f"core/groups/{group_pk}/add_user/", data={"pk": user_id})
                    added.append(group_name)
                    result.groups.append(group_name)
            except Exception as e:
                failed.append(f"{group_name} ({e})")

        parts = []
        if added:
            parts.append(f"added: {', '.join(added)}")
        if already:
            parts.append(f"already in: {', '.join(already)}")
        if failed:
            parts.append(f"failed: {', '.join(failed)}")

        status = StepStatus.FAILED if failed and not added else StepStatus.SUCCESS
        result.add(step, status, "; ".join(parts))

    def _step_mailcow_create(self, email: str, name: str, company_cfg: CompanyConfig, result: ChainResult) -> None:
        step = "Mailcow mailbox"
        if self.dry_run:
            result.add(step, StepStatus.SKIPPED, "dry-run")
            return

        mailcow_url = company_cfg.mailcow_url or self.config.mailcow.api_url
        if not mailcow_url:
            result.add(step, StepStatus.SKIPPED, "no mailcow_url for this company")
            return

        api_key = ""
        if company_cfg.mailcow_key_env:
            api_key = os.getenv(company_cfg.mailcow_key_env, "")
        if not api_key:
            api_key = self.mailcow_api_key
        if not api_key:
            key_hint = company_cfg.mailcow_key_env or "MAILCOW_API_KEY"
            result.add(step, StepStatus.SKIPPED, f"no {key_hint} configured")
            return

        mc = MailcowProvisionClient(api_url=mailcow_url, api_key=api_key)

        if mc.mailbox_exists(email):
            mailbox = mc.get_mailbox(email)
            if mailbox and str(mailbox.get("active")) != "1":

                def _enable() -> None:
                    if not mc.enable_mailbox(email):
                        raise RuntimeError("Mailcow enable_mailbox returned failure")

                if self._retry(_enable, step, result):
                    result.add(step, StepStatus.SUCCESS, "re-enabled")
            else:
                result.add(step, StepStatus.SKIPPED, "already exists")
            return

        quota = self.config.defaults.mailbox_quota

        def _create_or_enable() -> None:
            if mc.create_mailbox(email=email, name=name, quota=quota):
                return
            # Creation failed — mailbox may exist in soft-deleted state. Try enable.
            if mc.enable_mailbox(email):
                return
            raise RuntimeError("Mailcow create and enable both failed")

        if self._retry(_create_or_enable, step, result):
            result.mailbox_quota_gb = quota // (1024 * 1024 * 1024)
            result.add(
                step, StepStatus.SUCCESS, f"created ({result.mailbox_quota_gb}GB quota, authsource: generic-oidc)"
            )

    def _step_odoo_sync(
        self,
        email: str,
        name: str,
        company_code: str,
        company_cfg: CompanyConfig,
        result: ChainResult,
    ) -> None:
        for target in company_cfg.odoo_targets:
            step = f"Odoo {target}"

            # Skip source HRMS
            if company_cfg.hrms and target == company_cfg.hrms:
                result.add(step, StepStatus.SKIPPED, "source HRMS")
                continue

            if self.dry_run:
                result.add(step, StepStatus.SKIPPED, "dry-run")
                continue

            creds = self.odoo_credentials.get(target)
            if not creds:
                result.add(step, StepStatus.SKIPPED, "no credentials configured")
                continue

            odoo = OdooProvisionClient(
                base_url=f"https://{target}",
                database=creds["database"],
                username=creds.get("username", "admin"),
                api_key=creds["api_key"],
            )

            if odoo.user_exists(email):
                user = odoo.get_user(email)
                if user and not user.get("active"):

                    def _activate(o: OdooProvisionClient = odoo, e: str = email) -> None:
                        if not o.activate_user(e):
                            raise RuntimeError("Odoo activate_user returned failure")

                    if self._retry(_activate, step, result):
                        result.add(step, StepStatus.SUCCESS, "reactivated")
                else:
                    result.add(step, StepStatus.SKIPPED, "already exists")
            else:

                def _create(o: OdooProvisionClient = odoo, e: str = email, n: str = name) -> None:
                    o.create_portal_user(e, n)

                if self._retry(_create, step, result):
                    result.add(step, StepStatus.SUCCESS, "portal user created")

    def _step_recovery_link(self, user_id: int, result: ChainResult) -> None:
        step = "Recovery link"
        try:
            resp = self.ak.post(f"core/users/{user_id}/recovery/", data={})
            link = resp.get("link", "")
            if link:
                result.recovery_link = link
                result.add(step, StepStatus.SUCCESS, "generated (7 days expiry)")
            else:
                result.add(step, StepStatus.FAILED, "no link returned")
        except Exception as e:
            result.add(step, StepStatus.FAILED, str(e))

    # --- OFFBOARD ---

    def offboard(self, email: str, company: str | None = None) -> ChainResult:
        """Disable user across all systems."""
        result = ChainResult(email=email, action="offboard")
        _, company_cfg = self._company_config(email, company)

        self.output.header(f"Deprovisioning {email}")

        # Step 1: Find and disable in Authentik
        user_id = self._step_ak_disable(email, result)
        if user_id is None and not self.dry_run:
            return result

        # Step 2: Kill sessions
        if user_id and not self.dry_run:
            self._step_ak_kill_sessions(user_id, result)

        # Step 3: Disable Mailcow
        self._step_mailcow_disable(email, company_cfg, result)

        # Step 4: Deactivate Odoo
        self._step_odoo_deactivate(email, result)

        # Notify admin via Telegram
        if not self.dry_run:
            _send_telegram_notification(result)

        return result

    def _step_ak_disable(self, email: str, result: ChainResult) -> int | None:
        step = "Authentik disable"
        if self.dry_run:
            result.add(step, StepStatus.SKIPPED, "dry-run")
            return None

        existing = self.ak.get("core/users/", params={"email": email})
        users = existing.get("results", [])

        if not users:
            result.add(step, StepStatus.FAILED, "user not found in Authentik")
            return None

        user = users[0]
        pk = user["pk"]

        if not user.get("is_active"):
            result.add(step, StepStatus.SKIPPED, "already inactive")
            return pk

        self.ak.patch(f"core/users/{pk}/", data={"is_active": False})
        result.add(step, StepStatus.SUCCESS, "is_active=false")
        return pk

    def _step_ak_kill_sessions(self, user_id: int, result: ChainResult) -> None:
        step = "Kill sessions"
        try:
            sessions = self.ak.get("core/authenticated_sessions/", params={"user": user_id})
            count = len(sessions.get("results", []))
            for s in sessions.get("results", []):
                self.ak.delete(f"core/authenticated_sessions/{s['uuid']}/")
            result.add(step, StepStatus.SUCCESS, f"{count} sessions terminated")
        except Exception as e:
            result.add(step, StepStatus.FAILED, str(e))

    def _step_mailcow_disable(self, email: str, company_cfg: CompanyConfig, result: ChainResult) -> None:
        step = "Mailcow disable"
        if self.dry_run:
            result.add(step, StepStatus.SKIPPED, "dry-run")
            return

        mailcow_url = company_cfg.mailcow_url or self.config.mailcow.api_url
        if not mailcow_url:
            result.add(step, StepStatus.SKIPPED, "no mailcow_url for this company")
            return

        api_key = ""
        if company_cfg.mailcow_key_env:
            api_key = os.getenv(company_cfg.mailcow_key_env, "")
        if not api_key:
            api_key = self.mailcow_api_key
        if not api_key:
            key_hint = company_cfg.mailcow_key_env or "MAILCOW_API_KEY"
            result.add(step, StepStatus.SKIPPED, f"no {key_hint} configured")
            return

        mc = MailcowProvisionClient(api_url=mailcow_url, api_key=api_key)

        if not mc.mailbox_exists(email):
            result.add(step, StepStatus.SKIPPED, "no mailbox found")
            return

        def _disable() -> None:
            mc.disable_mailbox(email)

        if self._retry(_disable, step, result):
            result.add(step, StepStatus.SUCCESS, "mailbox disabled")

    def _step_odoo_deactivate(self, email: str, result: ChainResult) -> None:
        try:
            company_code, company_cfg = self._company_config(email)
        except ValueError as e:
            result.add("Odoo deactivate", StepStatus.FAILED, str(e))
            return
        for target in company_cfg.odoo_targets:
            step = f"Odoo {target}"
            if self.dry_run:
                result.add(step, StepStatus.SKIPPED, "dry-run")
                continue

            creds = self.odoo_credentials.get(target)
            if not creds:
                result.add(step, StepStatus.SKIPPED, "no credentials")
                continue

            odoo = OdooProvisionClient(
                base_url=f"https://{target}",
                database=creds["database"],
                username=creds.get("username", "admin"),
                api_key=creds["api_key"],
            )

            if not odoo.user_exists(email):
                result.add(step, StepStatus.SKIPPED, "user not found")
                continue

            def _deactivate(o: OdooProvisionClient = odoo, e: str = email) -> None:
                if not o.deactivate_user(e):
                    raise RuntimeError("Odoo deactivate_user returned failure")

            if self._retry(_deactivate, step, result):
                result.add(step, StepStatus.SUCCESS, "user deactivated")
