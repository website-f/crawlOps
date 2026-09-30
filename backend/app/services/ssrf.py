"""SSRF egress guard for the crawler + media fetchers.

User-supplied URLs (RSS/watchlist feeds, crawled media) must not be able to reach
internal-only targets: cloud metadata (169.254.169.254), loopback, RFC1918/ULA, or
our own service ports (postgres/redis/meili/minio). We resolve the host and reject
any private/loopback/link-local/reserved address. A small allowlist keeps the
legitimately-internal data services (RSSHub, FlareSolverr, camofox, loginsvc)
reachable, since connectors fetch through them on purpose.
"""
import ipaddress
import socket
from urllib.parse import urlparse

from ..config import settings

# hostnames of the internal services connectors are allowed to talk to directly
_ALLOW_HOSTS: set[str] = set()
for _u in (settings.rsshub_url, settings.flaresolverr_url, settings.camofox_url,
           settings.loginsvc_url, settings.meili_url):
    try:
        _h = urlparse(_u).hostname
        if _h:
            _ALLOW_HOSTS.add(_h.lower())
    except Exception:  # noqa: BLE001
        pass


class BlockedURL(ValueError):
    """Raised when a URL points at a non-public / disallowed target."""


def _ip_is_public(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def guard_url(url: str) -> None:
    """Raise BlockedURL unless `url` is a public http(s) endpoint (or an allowlisted
    internal service). Resolves every A/AAAA record so a DNS-rebind to an internal
    IP is caught too."""
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise BlockedURL(f"blocked scheme: {u.scheme or 'none'}")
    host = (u.hostname or "").lower()
    if not host:
        raise BlockedURL("no host in url")
    if host in _ALLOW_HOSTS:
        return  # trusted internal data service (rsshub etc.)
    # bare-IP hosts: check directly (no DNS)
    try:
        ipaddress.ip_address(host)
        if not _ip_is_public(host):
            raise BlockedURL(f"blocked internal address: {host}")
        return
    except ValueError:
        pass  # not a literal IP -> resolve below
    try:
        infos = socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise BlockedURL(f"dns resolution failed for {host}") from e
    for info in infos:
        addr = info[4][0]
        if not _ip_is_public(addr):
            raise BlockedURL(f"blocked internal address {addr} for host {host}")
