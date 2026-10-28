"""Opt-in URL policy helpers for deployments that browse untrusted URLs.

This is a defense-in-depth filter, not a complete SSRF boundary. DNS can change
between validation and Chromium's connection; enforce outbound network policy
outside the process as well.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit
from typing import Callable, Iterable


class PublicURLRejected(ValueError):
    """Raised when a URL is outside the public HTTP(S) URL policy."""


def validate_public_url(
    url: str,
    resolver: Callable[..., Iterable[tuple]] = socket.getaddrinfo,
) -> None:
    """Allow HTTP(S) URLs whose host resolves exclusively to globally routable IPs.

    Every request is checked, including redirects and browser subresources, when
    used as a Playwright route handler. Network-level egress filtering is still
    required to close DNS-rebinding/TOCTOU gaps and constrain browser traffic.
    """
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        # Accessing .port also validates malformed port syntax.
        parsed.port
    except ValueError as exc:
        raise PublicURLRejected("malformed URL") from exc

    if scheme not in {"http", "https"}:
        raise PublicURLRejected("only HTTP and HTTPS URLs are allowed")
    if not host:
        raise PublicURLRejected("URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise PublicURLRejected("URLs containing credentials are not allowed")

    host = host.rstrip(".")
    if not host or host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise PublicURLRejected("local hostnames are not allowed")

    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None

    if literal is not None:
        addresses = [literal]
    else:
        try:
            results = resolver(host, parsed.port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = [ipaddress.ip_address(item[4][0].split("%", 1)[0]) for item in results]
        except (OSError, ValueError, IndexError, TypeError) as exc:
            raise PublicURLRejected("hostname could not be safely resolved") from exc
        if not addresses:
            raise PublicURLRejected("hostname returned no addresses")

    if any(
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        for address in addresses
    ):
        raise PublicURLRejected("URL resolves to a non-public IP address")
