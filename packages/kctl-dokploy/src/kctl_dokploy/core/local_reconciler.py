"""Reconciler for ``kctl-dokploy deploy apply-local``.

Given a :class:`~kctl_dokploy.core.manifest.DeployManifest` targeting local
infrastructure, converge:

1. Cloudflare wildcard A records (``*.local.kodeme.io``, ``local.kodeme.io``)
   to the workstation's current LAN IP.
2. Dokploy project, environment, and compose service (via existing
   :mod:`kctl_dokploy.core.deploy_ops` helpers).
3. Dokploy env file push.
4. Dokploy domain attachment with ``cert_type=none`` so Traefik falls back to
   its default (wildcard) certificate store.

External dependencies are injected for testability:
  * :class:`DnsAdapter` — Cloudflare DNS get/update.
  * A Dokploy adapter exposing ``ensure_compose``/``push_env`` and a
    ``.domains`` sub-adapter (see :class:`LocalDokployAdapter`).
  * A callable returning the current LAN IP.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

from kctl_dokploy.core import deploy_ops
from kctl_dokploy.core.lan_ip import is_private_ipv4

if TYPE_CHECKING:  # pragma: no cover
    from kctl_dokploy.core.manifest import DeployManifest

__all__ = [
    "DnsAdapter",
    "KctlCfDnsAdapter",
    "LocalDokployAdapter",
    "LocalReconciler",
    "ReconcileResult",
]


# ---------------------------------------------------------------------------
# DNS adapter protocol
# ---------------------------------------------------------------------------


class DnsAdapter(Protocol):
    """Minimal DNS read/update interface for Cloudflare A records."""

    def get(self, zone: str, name: str) -> str | None: ...

    def update(self, zone: str, name: str, content: str) -> None: ...


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ReconcileResult:
    """Outcome of a reconcile step — used to decide whether to trigger a redeploy."""

    changed: bool = False
    inspected: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------


@dataclass
class LocalReconciler:
    """Converge local-infra resources declared by a manifest.

    Attributes:
        dns: Cloudflare DNS adapter.
        dokploy: Dokploy-side adapter (see :class:`LocalDokployAdapter`).
        lan_ip_getter: Callable that returns the current workstation LAN IPv4.
        zone: Cloudflare zone name (default ``kodeme.io``).
    """

    dns: DnsAdapter
    dokploy: Any  # ensure_compose / push_env / .domains.*
    lan_ip_getter: Callable[[], IPv4Address]
    zone: str = "kodeme.io"

    WILDCARD_NAME = "*.local.kodeme.io"
    APEX_NAME = "local.kodeme.io"
    _LOCAL_SUFFIX = ".local.kodeme.io"

    # -- Step 1: DNS --------------------------------------------------------

    def reconcile_dns(self) -> ReconcileResult:
        """Ensure the Cloudflare wildcard + apex A records match the current LAN IP."""
        result = ReconcileResult()
        lan_ip = self.lan_ip_getter()
        if not is_private_ipv4(str(lan_ip)):
            raise ValueError(f"Current LAN IP {lan_ip} is not RFC1918; refusing to publish.")

        for name in (self.WILDCARD_NAME, self.APEX_NAME):
            result.inspected.append(name)
            live = self.dns.get(self.zone, name)
            if live != str(lan_ip):
                self.dns.update(self.zone, name, str(lan_ip))
                result.changed = True
                result.messages.append(f"{name}: {live!r} -> {lan_ip}")

        return result

    # -- Step 4: Domain -----------------------------------------------------

    def reconcile_domain(
        self,
        compose_id: str,
        host: str,
        port: int,
        service: str,
    ) -> ReconcileResult:
        """Ensure a Dokploy domain with the given spec is attached to the compose service.

        Uses ``cert_type='none'`` so Traefik falls back to the default cert
        store (populated by ``wildcard-local.yml`` → our ``*.local.kodeme.io``
        certificate).
        """
        if not host.endswith(self._LOCAL_SUFFIX):
            raise ValueError(f"host {host!r} must end with {self._LOCAL_SUFFIX}")

        spec: dict[str, Any] = {
            "host": host,
            "port": port,
            "service_name": service,
            "https": True,
            "cert_type": "none",
        }
        existing = self.dokploy.domains.list_for_compose(compose_id)
        for d in existing:
            if all(d.get(k) == v for k, v in spec.items()):
                return ReconcileResult(changed=False, inspected=[host])

        self.dokploy.domains.create(compose_id=compose_id, **spec)
        return ReconcileResult(
            changed=True,
            inspected=[host],
            messages=[f"domain created: {host}"],
        )

    # -- End-to-end ---------------------------------------------------------

    def apply(self, manifest: DeployManifest) -> ReconcileResult:
        """Converge all resources declared by *manifest* (local-only).

        Steps (in order):
          1. :meth:`reconcile_dns` — wildcard CF records point to current LAN IP.
          2. ``dokploy.ensure_compose`` — project + environment + compose exist.
          3. ``dokploy.push_env`` — env_file content mirrored to the compose service.
          4. :meth:`reconcile_domain` — Dokploy domain attached with ``cert_type=none``.
        """
        if manifest.environment != "local":
            raise ValueError(f"apply() refuses non-local manifest (environment={manifest.environment!r})")

        overall = ReconcileResult()

        dns_r = self.reconcile_dns()
        overall.changed |= dns_r.changed
        overall.messages.extend(dns_r.messages)

        compose = self.dokploy.ensure_compose(manifest)
        overall.changed |= bool(compose.get("changed"))
        compose_id: str = compose["compose_id"]

        env = self.dokploy.push_env(compose_id, manifest.env_file)
        overall.changed |= bool(env.get("changed"))

        # `manifest.domain` is always present on DeployManifest (has defaults);
        # treat empty host as "no domain declared".
        if manifest.domain and manifest.domain.host:
            dom_r = self.reconcile_domain(
                compose_id=compose_id,
                host=manifest.domain.host,
                port=manifest.domain.port,
                service=manifest.domain.service,
            )
            overall.changed |= dom_r.changed
            overall.messages.extend(dom_r.messages)

        return overall


# ---------------------------------------------------------------------------
# Cloudflare DNS adapter — shells out to `kctl-cf`
# ---------------------------------------------------------------------------


@dataclass
class KctlCfDnsAdapter:
    """DnsAdapter backed by the ``kctl-cf`` CLI.

    ``kctl-cf records get`` requires a record ID, so to get-by-name we list
    records in the zone and filter. ``kctl-cf records update`` likewise
    requires a record ID.
    """

    profile: str = "kodemeio"

    def _find_record(self, zone: str, name: str) -> dict[str, Any] | None:
        proc = subprocess.run(
            ["kctl-cf", "-p", self.profile, "--json", "records", "list", "--zone", zone],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None
        try:
            records = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(records, list):
            return None
        for rec in records:
            if isinstance(rec, dict) and rec.get("name") == name:
                return rec
        return None

    def get(self, zone: str, name: str) -> str | None:
        rec = self._find_record(zone, name)
        if rec is None:
            return None
        content = rec.get("content")
        return str(content) if content else None

    def update(self, zone: str, name: str, content: str) -> None:
        rec = self._find_record(zone, name)
        if rec is None or not rec.get("id"):
            raise RuntimeError(f"kctl-cf: record {name!r} not found in zone {zone!r}")
        record_id = str(rec["id"])
        subprocess.run(
            [
                "kctl-cf",
                "-p",
                self.profile,
                "records",
                "update",
                record_id,
                "--zone",
                zone,
                "--name",
                name,
                "--content",
                content,
            ],
            check=True,
            capture_output=True,
            text=True,
        )


# ---------------------------------------------------------------------------
# Dokploy adapter — thin wrapper over `deploy_ops`
# ---------------------------------------------------------------------------


class _DomainsAdapter:
    """Sub-adapter exposed at ``adapter.domains.*``.

    Delegates to module-level helpers in :mod:`kctl_dokploy.core.deploy_ops`.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def list_for_compose(self, compose_id: str) -> list[dict[str, Any]]:
        # XXX(local-domains): expects deploy_ops.list_domains_for_compose — added in this task.
        return deploy_ops.list_domains_for_compose(self._client, compose_id)

    def create(self, *, compose_id: str, **spec: Any) -> None:
        # XXX(local-domains): expects deploy_ops.create_domain — added in this task.
        deploy_ops.create_domain(self._client, compose_id=compose_id, **spec)

    def update(self, domain_id: str, **spec: Any) -> None:
        # XXX(local-domains): expects deploy_ops.update_domain — added in this task.
        deploy_ops.update_domain(self._client, domain_id=domain_id, **spec)


@dataclass
class LocalDokployAdapter:
    """Dokploy side of the reconciler — wraps existing :mod:`deploy_ops` helpers."""

    client: Any

    def __post_init__(self) -> None:
        self.domains = _DomainsAdapter(self.client)

    def ensure_compose(self, manifest: DeployManifest) -> dict[str, Any]:
        # XXX(local-domains): expects deploy_ops.ensure_project_and_env + ensure_compose_service.
        env_info = deploy_ops.ensure_project_and_env(self.client, manifest)
        return deploy_ops.ensure_compose_service(self.client, manifest, env_info)

    def push_env(self, compose_id: str, env_file_path: Path | str | None) -> dict[str, Any]:
        # XXX(local-domains): expects deploy_ops.push_env_file(client, compose_id, path, force=True).
        return deploy_ops.push_env_file(self.client, compose_id, env_file_path, force=True)
