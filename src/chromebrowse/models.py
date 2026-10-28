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

@dataclass
class TableCell:
    """One cell of an extracted table."""

    text: str = ""
    header: bool = False
    colspan: int = 1
    rowspan: int = 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "header": self.header,
            "colspan": self.colspan,
            "rowspan": self.rowspan,
        }


@dataclass
class Table:
    """A table extracted from the rendered DOM.

    ``rows`` holds every row including the header row. ``columns`` is the
    number of distinct cell slots in the widest row, which is what callers
    normally want when deciding whether a table is regular.
    """

    index: int = 0
    caption: str = ""
    headers: List[str] = field(default_factory=list)
    rows: List[List[TableCell]] = field(default_factory=list)
    columns: int = 0

    @property
    def data_rows(self) -> List[List[TableCell]]:
        """Rows after the header row, if one was detected."""
        if self.rows and all(c.header for c in self.rows[0]):
            return self.rows[1:]
        return list(self.rows)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "caption": self.caption,
            "headers": list(self.headers),
            "rows": [[c.as_dict() for c in row] for row in self.rows],
            "columns": self.columns,
        }


@dataclass
class JsonLdBlock:
    """One ``application/ld+json`` script block.

    ``data`` is the parsed JSON value as-is (dict, list, or scalar). ``error``
    is set when the block was present but not valid JSON, so callers can tell
    "no structured data" apart from "broken structured data".
    """

    index: int = 0
    data: Any = None
    error: Optional[str] = None

    @property
    def types(self) -> List[str]:
        """Flattened ``@type`` values found in this block."""
        found: List[str] = []
        items = self.data if isinstance(self.data, list) else [self.data]
        for item in items:
            if isinstance(item, dict):
                value = item.get("@type")
                if isinstance(value, str):
                    found.append(value)
                elif isinstance(value, list):
                    found.extend(v for v in value if isinstance(v, str))
        return found

    def as_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "data": self.data, "error": self.error}
