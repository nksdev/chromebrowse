"""URL normalization and crawl scope rules.

Scope is a *policy* control owned by the caller. It limits accidental
traversal; it is not an authorization mechanism and does not establish that
a site permits crawling. See ``docs/SECURITY.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Pattern, Set, Union
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str, base: Optional[str] = None) -> str:
    """Return a canonical form of ``url`` for deduplication.

    The transformation is conservative: it lowercases scheme/host, strips
    default ports, drops fragments and common tracking parameters, and sorts
    remaining query parameters. It never changes the path, so distinct
    resources stay distinct.

    Raises:
        ValueError: if the URL is not absolute http(s) after joining ``base``.
    """
    if base:
        url = urljoin(base, url)
    url, _fragment = urldefrag(url.strip())
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme {scheme!r} in {url!r}")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError(f"URL has no host: {url!r}")
    port = parts.port
    netloc = host
    if port and port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"
    query = _clean_query(parts.query)
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def _clean_query(query: str) -> str:
    if not query:
        return ""
    kept = []
    for pair in query.split("&"):
        if not pair:
            continue
        key = pair.split("=", 1)[0]
        if key.lower().startswith(_TRACKING_PREFIXES):
            continue
        kept.append(pair)
    return "&".join(sorted(kept))


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


@dataclass
class CrawlScope:
    """Decide which URLs a crawl may visit.

    Args:
        allow_domains: Domains that are in scope. A bare domain also allows
            its subdomains; prefix an entry with ``"."`` to be explicit.
        allow_pattern: Optional regex the full URL must match.
        deny_pattern: Optional regex; a match excludes the URL.
        same_domain_only: When true, only the seed host is in scope and
            ``allow_domains`` is ignored.
    """

    allow_domains: Set[str] = field(default_factory=set)
    allow_pattern: Optional[Union[str, Pattern[str]]] = None
    deny_pattern: Optional[Union[str, Pattern[str]]] = None
    same_domain_only: bool = True
    seed_host: str = ""

    def __post_init__(self) -> None:
        self.allow_domains = {d.lower().lstrip(".") for d in self.allow_domains}
        self.allow_pattern = _compile(self.allow_pattern)
        self.deny_pattern = _compile(self.deny_pattern)

    def with_seed(self, url: str) -> "CrawlScope":
        """Return a copy anchored on the seed URL's host."""
        clone = CrawlScope(
            allow_domains=set(self.allow_domains),
            allow_pattern=self.allow_pattern,
            deny_pattern=self.deny_pattern,
            same_domain_only=self.same_domain_only,
            seed_host=host_of(url),
        )
        if clone.same_domain_only and clone.seed_host:
            clone.allow_domains.add(clone.seed_host)
        return clone

    def allows(self, url: str) -> bool:
        """True if ``url`` is inside the configured scope."""
        host = host_of(url)
        if not host:
            return False
        if not self._domain_ok(host):
            return False
        if self.allow_pattern is not None and not self.allow_pattern.search(url):
            return False
        if self.deny_pattern is not None and self.deny_pattern.search(url):
            return False
        return True

    def _domain_ok(self, host: str) -> bool:
        if not self.allow_domains:
            return False
        return any(host == d or host.endswith("." + d) for d in self.allow_domains)


def _compile(value: Optional[Union[str, Pattern[str]]]) -> Optional[Pattern[str]]:
    if value is None or hasattr(value, "search"):
        return value  # type: ignore[return-value]
    return re.compile(value)
