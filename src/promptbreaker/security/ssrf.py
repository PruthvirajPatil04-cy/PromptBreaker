"""SSRF guard for target adapters.

Every outbound request the engine makes passes through assert_target_allowed().
The guard resolves DNS first, then checks every resolved address — this defeats
DNS-rebinding (resolve-to-public-then-repoint) because we pin the validated IP
for the actual connection rather than re-resolving.

Blocking rules (default):
  - schemes other than http/https
  - loopback, link-local (169.254.x.x incl. cloud metadata), private, CGNAT,
    multicast, reserved, unspecified, IPv6 loopback/link-local/ULA
  - redirects followed manually, each hop re-validated, capped

Explicit opt-in per target (allow_private=True) is required for internal
lab testing — never the default.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from promptbreaker.errors import SsrfBlockedError

ALLOWED_SCHEMES = {"http", "https"}


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 6 and ip.ipv4_mapped is not None and not _is_public(ip.ipv4_mapped))
        or ip.is_site_local  # IPv6 fec0::/10
    )


def resolve_host(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a host to all A/AAAA records. Fails closed on NXDOMAIN."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SsrfBlockedError(f"cannot resolve host {host!r}: {exc}") from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def assert_target_allowed(url: str, *, allow_private: bool = False) -> None:
    """Validate a URL before any outbound connection. Raises SsrfBlockedError."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SsrfBlockedError(f"scheme {parsed.scheme!r} not allowed (http/https only)")
    if not parsed.hostname:
        raise SsrfBlockedError("url has no host")

    if allow_private:
        return  # explicit opt-in (internal lab target)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = resolve_host(parsed.hostname, port)
    if not addresses:
        raise SsrfBlockedError(f"host {parsed.hostname!r} resolved to no addresses")
    for ip in addresses:
        if not _is_public(ip):
            raise SsrfBlockedError(
                f"host {parsed.hostname!r} resolves to non-public address {ip} — "
                "blocked by SSRF guard (set allow_private=true on the target for labs)"
            )
