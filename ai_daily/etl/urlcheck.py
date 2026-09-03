"""Guard against fetching operator-supplied URLs that point inside the network."""

import ipaddress
import socket
from urllib.parse import urlparse


def ensure_public_http_url(url: str) -> None:
    """Raise ValueError unless url is http(s) and resolves only to public addresses.

    Cloud metadata endpoints, loopback and RFC 1918 ranges are the usual SSRF
    targets; every resolved address must fall outside them.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise ValueError("URL has no host")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve host: {parsed.hostname}") from e
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError(f"Refusing to fetch a non-public address ({address})")
