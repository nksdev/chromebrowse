"""Bounded, deduplicating breadth-first URL queue."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Set, Tuple


@dataclass(order=True)
class QueueItem:
    depth: int
    url: str
    parent: Optional[str] = None


class CrawlQueue:
    """FIFO queue that refuses duplicates and enforces depth/max-page limits.

    Deduplication is by *normalized* URL, so ``/a`` and ``/a#top`` count as
    one page. The queue is bounded by ``max_pages``: once that many unique
    URLs have been enqueued, further URLs are rejected and the caller's
    ``skipped_limit`` counter is incremented by :meth:`push` returning
    ``PushOutcome.LIMIT``.
    """

    def __init__(self, max_pages: int, max_depth: int) -> None:
        if max_pages <= 0:
            raise ValueError(f"max_pages must be > 0, got {max_pages!r}")
        if max_depth < 0:
            raise ValueError(f"max_depth must be >= 0, got {max_depth!r}")
        self.max_pages = max_pages
        self.max_depth = max_depth
        self._queue: Deque[QueueItem] = deque()
        self._seen: Set[str] = set()
        self._depths: Dict[str, int] = {}

    def push(self, url: str, depth: int, parent: Optional[str] = None) -> str:
        """Enqueue ``url`` and return one of ``ok``/``duplicate``/``depth``/``limit``."""
        if url in self._seen:
            return "duplicate"
        if depth > self.max_depth:
            return "depth"
        if len(self._seen) >= self.max_pages:
            return "limit"
        self._seen.add(url)
        self._depths[url] = depth
        self._queue.append(QueueItem(depth=depth, url=url, parent=parent))
        return "ok"

    def pop(self) -> Optional[QueueItem]:
        return self._queue.popleft() if self._queue else None

    def __len__(self) -> int:
        return len(self._queue)

    @property
    def seen_count(self) -> int:
        return len(self._seen)

    def seen(self) -> List[str]:
        return sorted(self._seen)

    def depth_of(self, url: str) -> int:
        return self._depths.get(url, -1)
