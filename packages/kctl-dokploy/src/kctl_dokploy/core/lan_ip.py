"""Determine the workstation's current LAN IPv4.

Used by the local-domains reconciler to compare declared vs live Cloudflare
A records for ``*.local.kodeme.io``.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from ipaddress import IPv4Address

__all__ = ["current_lan_ipv4", "is_private_ipv4"]

_SRC_RE = re.compile(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)\b")


def is_private_ipv4(addr: str) -> bool:
    """Return True if *addr* is a private IPv4 address (RFC1918, not loopback/link-local)."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return isinstance(ip, IPv4Address) and ip.is_private and not ip.is_loopback and not ip.is_link_local


def _run_ip_route() -> str:
    """Return stdout of ``ip -4 -o route get 1.1.1.1``.

    Broken out so tests can patch it without touching ``subprocess``.
    """
    return subprocess.run(
        ["ip", "-4", "-o", "route", "get", "1.1.1.1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def current_lan_ipv4() -> IPv4Address:
    """Return the workstation's outbound-facing IPv4.

    Parses the ``src <ip>`` token from ``ip route get``. Raises
    :class:`RuntimeError` when the token is missing.
    """
    out = _run_ip_route()
    m = _SRC_RE.search(out)
    if not m:
        raise RuntimeError(f"Could not determine LAN IP from `ip route get` output: {out!r}")
    return IPv4Address(m.group(1))
