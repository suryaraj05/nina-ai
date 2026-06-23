"""SSRF guard: validate that an outbound URL targets a public host.

Framework-agnostic (raises ``SsrfError``, not an HTTP exception) so it can be
shared by the console API layer and the runtime action executor. Unlike a
bare IP-literal check, this resolves the hostname via DNS and verifies *every*
resolved address, closing the "hostname that points at an internal IP" and
DNS-rebinding-at-config-time holes.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private, loopback, link-local (incl. cloud metadata 169.254.169.254), and
# unique-local ranges that must never be reachable from a server-side fetch.
_BLOCKED_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),    # carrier-grade NAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique-local
]


class SsrfError(ValueError):
    """Raised when a URL is rejected as a potential SSRF target."""


def _is_blocked_ip(addr: ipaddress._BaseAddress) -> bool:
    # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) must be checked as IPv4.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if addr.is_loopback or addr.is_link_local or addr.is_private or addr.is_reserved:
        return True
    return any(addr in net for net in _BLOCKED_NETS)


def validate_public_url(url: str, label: str = "URL") -> None:
    """Raise SsrfError if *url* is not a well-formed http(s) URL pointing at a
    public host. Resolves DNS and rejects if any resolved address is internal."""
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise SsrfError(f"Invalid {label}.") from exc
    if parsed.scheme not in ("http", "https"):
        raise SsrfError(f"{label} must use http or https.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise SsrfError(f"{label} must have a hostname.")
    if host == "localhost":
        raise SsrfError(f"Internal {label.lower()} is not allowed.")

    # If the host is a bare IP literal, check it directly.
    try:
        addr = ipaddress.ip_address(host)
        if _is_blocked_ip(addr):
            raise SsrfError(f"Internal {label.lower()} is not allowed.")
        return
    except ValueError:
        pass  # not a literal — resolve it below

    # Resolve the hostname and reject if ANY resolved address is internal.
    try:
        infos = socket.getaddrinfo(host, parsed.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SsrfError(f"Could not resolve {label.lower()} host.") from exc
    for info in infos:
        sockaddr = info[4]
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _is_blocked_ip(addr):
            raise SsrfError(f"Internal {label.lower()} is not allowed.")
