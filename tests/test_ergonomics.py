"""Regression tests for ergonomic API additions (no browser launch)."""

import pytest

from chromebrowse.browser import Browser, Element, Page
from chromebrowse.exceptions import ElementNotFoundError
from chromebrowse.extract import EXTRACT_META_JS, html_to_markdown


class FakeLocator:
    def __init__(self, count=0):
        self._count = count

    def count(self):
        return self._count

    def nth(self, index):
        return self


class FakePWPage:
    def __init__(self, counts=None):
        self.counts = counts or {}

    def locator(self, selector):
        return FakeLocator(self.counts.get(selector, 0))

    def evaluate(self, script, arg=None):
        if script is EXTRACT_META_JS:
            return {"description": "d", "title": "t"}
        return []


def _page(counts=None):
    browser = Browser()
    return Page(browser, FakePWPage(counts))


def test_find_required_false_returns_none():
    page = _page({"h1": 0})
    assert page.find("h1", required=False) is None


def test_find_required_false_returns_default():
    page = _page({"h1": 0})
    sentinel = object()
    assert page.find("h1", required=False, default=sentinel) is sentinel


def test_find_still_raises_by_default():
    page = _page({"h1": 0})
    with pytest.raises(ElementNotFoundError):
        page.find("h1")


def test_find_returns_element_when_present():
    page = _page({"h1": 1})
    assert isinstance(page.find("h1"), Element)


def test_table_missing_raises_element_not_found():
    page = _page()
    page.tables = lambda selector=None: []
    with pytest.raises(ElementNotFoundError):
        page.table("#missing")


def test_extract_markdown_without_html():
    page = _page()
    page.current_url = lambda: "https://x.test"
    type(page).title = property(lambda self: "T")
    page.text = lambda: "hello"
    page.content = lambda: '<p>hello <a href="https://x.test">link</a></p>'
    page.meta = lambda: {}

    content = page.extract(include_markdown=True)

    assert content.html == ""
    assert "[link](https://x.test)" in content.markdown


def test_batch_records_errors_and_replaces_failed_tabs(monkeypatch):
    browser = Browser()
    browser._started = True
    created = []

    class Tab:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        def extract(self, **kwargs):
            return "content"

    def new_page():
        tab = Tab()
        created.append(tab)
        return tab

    monkeypatch.setattr(browser, "new_page", new_page)

    def navigate(page, url, **kwargs):
        if "bad" in url:
            raise RuntimeError("boom")
        return page

    monkeypatch.setattr(browser, "_navigate", navigate)

    results = browser.batch(["https://good.test", "https://bad.test", "https://ok.test"])

    assert [r["ok"] for r in results] == [True, False, True]
    assert created[0].closed is True  # failed tab discarded
    # initial tab + one replacement after the failure; both get closed.
    assert len(created) == 2
