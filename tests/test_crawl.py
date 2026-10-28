"""Offline unit tests for the crawl building blocks.

These cover URL normalization, scope policy, queue bounds, and the Crawler
control flow with a fake page. A live end-to-end crawl against a local
``http.server`` is in ``tests/test_live_crawl.py`` (skipped without Chromium).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chromebrowse.crawl import CrawlQueue, CrawlScope, Crawler, normalize_url
from chromebrowse.crawl.models import CrawlPage, CrawlResult


# --------------------------------------------------------------------- scope


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://Example.COM/a", "https://example.com/a"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com/a#frag", "https://example.com/a"),
        ("https://example.com/a?utm_source=x&b=2&a=1", "https://example.com/a?a=1&b=2"),
        ("https://example.com", "https://example.com/"),
        ("https://example.com:8443/x", "https://example.com:8443/x"),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("bad", ["mailto:a@b.c", "javascript:void(0)", "/relative", ""])
def test_normalize_url_rejects_non_http(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


def test_normalize_url_joins_base():
    assert normalize_url("/b", base="https://example.com/a") == "https://example.com/b"


def test_scope_same_domain_default():
    scope = CrawlScope().with_seed("https://example.com/a")
    assert scope.allows("https://example.com/b")
    assert not scope.allows("https://other.com/b")


def test_scope_allows_subdomains_of_listed_domain():
    scope = CrawlScope(allow_domains={"example.com"}, same_domain_only=False)
    assert scope.allows("https://api.example.com/x")
    assert not scope.allows("https://notexample.com/x")


def test_scope_deny_pattern_wins():
    scope = CrawlScope(deny_pattern=r"/private/").with_seed("https://example.com/")
    assert scope.allows("https://example.com/public")
    assert not scope.allows("https://example.com/private/x")


def test_scope_allow_pattern_required():
    scope = CrawlScope(allow_pattern=r"/docs/").with_seed("https://example.com/")
    assert scope.allows("https://example.com/docs/a")
    assert not scope.allows("https://example.com/blog/a")


def test_scope_rejects_unknown_host():
    assert not CrawlScope(allow_domains={"example.com"}).allows("")


# --------------------------------------------------------------------- queue


def test_queue_deduplicates():
    q = CrawlQueue(max_pages=10, max_depth=2)
    assert q.push("https://a/", 0) == "ok"
    assert q.push("https://a/", 0) == "duplicate"
    assert len(q) == 1


def test_queue_rejects_beyond_max_depth():
    q = CrawlQueue(max_pages=10, max_depth=1)
    assert q.push("https://a/", 0) == "ok"
    assert q.push("https://b/", 2) == "depth"


def test_queue_rejects_beyond_max_pages():
    q = CrawlQueue(max_pages=2, max_depth=5)
    assert q.push("https://a/", 0) == "ok"
    assert q.push("https://b/", 0) == "ok"
    assert q.push("https://c/", 0) == "limit"


def test_queue_pops_in_fifo_order():
    q = CrawlQueue(max_pages=5, max_depth=5)
    q.push("https://a/", 0)
    q.push("https://b/", 1)
    assert q.pop().url == "https://a/"
    assert q.pop().url == "https://b/"
    assert q.pop() is None


@pytest.mark.parametrize("max_pages,max_depth", [(0, 0), (-1, 0), (1, -1)])
def test_queue_rejects_invalid_bounds(max_pages, max_depth):
    with pytest.raises(ValueError):
        CrawlQueue(max_pages=max_pages, max_depth=max_depth)


# -------------------------------------------------------------------- models


def test_crawl_page_as_dict_roundtrips():
    page = CrawlPage(url="https://a/", depth=1, status=200, title="t", text="x")
    assert json.loads(json.dumps(page.as_dict()))["url"] == "https://a/"
    assert page.ok


def test_crawl_result_counts_start_at_zero():
    result = CrawlResult()
    assert result.visited == 0 and result.failed == 0 and result.pages == []
    assert result.as_dict()["cancelled"] is False


# ------------------------------------------------------------------- crawler


class FakeLink:
    def __init__(self, href):
        self.href = href


class FakePage:
    """Minimal stand-in for ``chromebrowse.Page``."""

    def __init__(self, pages):
        self.pages = pages
        self.status = 200
        self.url = ""
        self.title = "title"
        self.goto_calls = []
        self.closed = False

    def goto(self, url, wait_until="load", timeout=None):
        self.goto_calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"404 {url}")
        self.url = url
        return self

    def current_url(self):
        return self.url

    def text(self):
        return "body"

    def links(self):
        return [FakeLink(h) for h in self.pages.get(self.url, [])]

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, pages):
        self.pages = pages
        self.page = FakePage(pages)
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


def test_crawler_visits_breadth_first_within_scope():
    site = {
        "https://example.com/": ["https://example.com/a", "https://example.com/b"],
        "https://example.com/a": ["https://example.com/a1"],
        "https://example.com/b": [],
        "https://example.com/a1": [],
    }
    browser = FakeBrowser(site)
    result = Crawler(max_pages=10, max_depth=2, browser=browser).crawl("https://example.com/")

    visited = [p.url for p in result.pages]
    assert visited == [
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a1",
    ]
    assert result.visited == 4 and result.failed == 0
    assert result.pages[0].links_enqueued == 2
    assert browser.page.closed
    assert not browser.closed  # caller-owned browser is not closed


def test_crawler_respects_max_depth():
    site = {
        "https://example.com/": ["https://example.com/a"],
        "https://example.com/a": ["https://example.com/deep"],
        "https://example.com/deep": [],
    }
    result = Crawler(max_pages=10, max_depth=1, browser=FakeBrowser(site)).crawl(
        "https://example.com/"
    )
    assert [p.url for p in result.pages] == ["https://example.com/", "https://example.com/a"]
    assert result.skipped_depth == 1


def test_crawler_skips_offscope_links():
    site = {
        "https://example.com/": ["https://evil.com/x", "https://example.com/ok"],
        "https://example.com/ok": [],
    }
    result = Crawler(max_pages=10, max_depth=2, browser=FakeBrowser(site)).crawl(
        "https://example.com/"
    )
    assert [p.url for p in result.pages] == ["https://example.com/", "https://example.com/ok"]
    assert result.skipped_offscope == 1


def test_crawler_records_page_errors_without_aborting():
    site = {"https://example.com/": ["https://example.com/broken"], "https://example.com/broken": None}
    browser = FakeBrowser(site)

    def goto(url, wait_until="load", timeout=None):
        browser.page.goto_calls.append(url)
        if url == "https://example.com/broken":
            raise ValueError("boom")
        browser.page.url = url
        return browser.page

    browser.page.goto = goto  # type: ignore[assignment]
    result = Crawler(max_pages=10, max_depth=2, browser=browser).crawl("https://example.com/")

    assert result.visited == 1
    assert result.failed == 1
    assert result.pages[1].error is not None
    assert len(result.errors) == 1


def test_crawler_honours_max_pages():
    site = {f"https://example.com/{i}": [] for i in range(10)}
    site["https://example.com/"] = [f"https://example.com/{i}" for i in range(10)]
    result = Crawler(max_pages=3, max_depth=2, browser=FakeBrowser(site)).crawl(
        "https://example.com/"
    )
    assert len(result.pages) == 3
    assert result.skipped_limit > 0


def test_crawler_cancel_stops_after_current_page():
    site = {
        "https://example.com/": ["https://example.com/a", "https://example.com/b"],
        "https://example.com/a": [],
        "https://example.com/b": [],
    }
    crawler = Crawler(max_pages=10, max_depth=2, browser=FakeBrowser(site))

    def on_page(record, result):
        crawler.cancel()

    crawler.on_page = on_page
    result = crawler.crawl("https://example.com/")
    assert result.cancelled is True
    assert len(result.pages) == 1


def test_crawler_resume_skips_previously_visited(tmp_path: Path):
    resume = tmp_path / "crawl.jsonl"
    resume.write_text(
        json.dumps({"url": "https://example.com/a"}) + "\n", encoding="utf-8"
    )
    site = {
        "https://example.com/": ["https://example.com/a", "https://example.com/b"],
        "https://example.com/b": [],
    }
    result = Crawler(
        max_pages=10, max_depth=2, browser=FakeBrowser(site), resume_path=resume
    ).crawl("https://example.com/")

    assert [p.url for p in result.pages] == ["https://example.com/", "https://example.com/b"]
    assert result.skipped_duplicate >= 1
    lines = [json.loads(l) for l in resume.read_text("utf-8").splitlines() if l.strip()]
    assert any(row["url"] == "https://example.com/" for row in lines)


def test_crawler_requires_a_seed():
    with pytest.raises(ValueError):
        Crawler(browser=FakeBrowser({})).crawl([])


def test_crawler_rejects_negative_delay():
    with pytest.raises(ValueError):
        Crawler(delay_seconds=-1)
