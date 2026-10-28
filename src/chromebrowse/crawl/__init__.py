"""Composable, browser-rendered crawling.

This package builds a crawler *on top of* the existing browser layer rather
than beside it. Everything here is policy-thin: URL normalization, scope
rules, a bounded queue, and a sequential render loop. It intentionally does
not implement HTTP fetching, concurrency, or ``robots.txt`` retrieval.

Public API::

    from chromebrowse.crawl import Crawler, CrawlScope, CrawlResult, CrawlPage
"""

from __future__ import annotations

from .crawler import Crawler
from .models import CrawlPage, CrawlResult
from .queue import CrawlQueue, QueueItem
from .scope import CrawlScope, host_of, normalize_url

__all__ = [
    "Crawler",
    "CrawlPage",
    "CrawlQueue",
    "CrawlResult",
    "CrawlScope",
    "QueueItem",
    "host_of",
    "normalize_url",
]
