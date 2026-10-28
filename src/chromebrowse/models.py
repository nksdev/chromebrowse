"""Dataclasses returned by the high-level API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Link:
    """A discovered hyperlink."""

    href: str
    text: str = ""
    title: str = ""
    rel: str = ""
    target: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "href": self.href,
            "text": self.text,
            "title": self.title,
            "rel": self.rel,
            "target": self.target,
        }


@dataclass
class PageContent:
    """Structured snapshot of rendered page content."""

    url: str = ""
    title: str = ""
    text: str = ""
    html: str = ""
    markdown: str = ""
    links: List[Link] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)
    lang: str = ""
    status: Optional[int] = None
    elapsed_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "html": self.html,
            "markdown": self.markdown,
            "links": [l.as_dict() for l in self.links],
            "meta": dict(self.meta),
            "lang": self.lang,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
        }

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"<PageContent url={self.url!r} title={self.title!r} chars={len(self.text)}>"


@dataclass
class Snapshot:
    """Screenshot capture result."""

    path: Optional[str] = None
    data: Optional[bytes] = None
    full_page: bool = False
    width: Optional[int] = None
    height: Optional[int] = None

    def __str__(self) -> str:  # pragma: no cover
        return f"<Snapshot path={self.path!r} bytes={len(self.data) if self.data else 0}>"