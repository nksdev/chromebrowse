"""Structured results produced by the crawler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CrawlPage:
    """One page visited during a crawl.

    ``error`` is set instead of the content fields when navigation or
    extraction failed; a failed page never aborts the whole crawl.
    """

    url: str
    final_url: str = ""
    depth: int = 0
    status: Optional[int] = None
    title: str = ""
    text: str = ""
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    links_found: int = 0
    links_enqueued: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "depth": self.depth,
            "status": self.status,
            "title": self.title,
            "text": self.text,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "links_found": self.links_found,
            "links_enqueued": self.links_enqueued,
        }


@dataclass
class CrawlResult:
    """Aggregate outcome of a crawl run."""

    pages: List[CrawlPage] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    visited: int = 0
    failed: int = 0
    skipped_offscope: int = 0
    skipped_duplicate: int = 0
    skipped_depth: int = 0
    skipped_limit: int = 0
    elapsed_ms: float = 0.0
    cancelled: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pages": [p.as_dict() for p in self.pages],
            "errors": list(self.errors),
            "visited": self.visited,
            "failed": self.failed,
            "skipped_offscope": self.skipped_offscope,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_depth": self.skipped_depth,
            "skipped_limit": self.skipped_limit,
            "elapsed_ms": self.elapsed_ms,
            "cancelled": self.cancelled,
        }
