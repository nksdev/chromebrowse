"""Regression tests for browser page-wrapper lifecycle."""

import pytest

from chromebrowse.browser import Browser, Page
from chromebrowse.exceptions import NavigationError


class FakePlaywrightPage:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_page_close_removes_wrapper_from_browser_registry():
    browser = Browser()
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    browser._pages.append(page)

    page.close()

    assert playwright_page.closed is True
    assert page not in browser._pages


def test_page_close_is_idempotent():
    browser = Browser()
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    browser._pages.append(page)

    page.close()
    page.close()

    assert page not in browser._pages
    assert browser._pages == []


def test_open_closes_new_page_when_navigation_fails(monkeypatch):
    browser = Browser()
    monkeypatch.setattr(browser, "start", lambda: browser)
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    monkeypatch.setattr(browser, "new_page", lambda: _register(browser, page))

    def fail_navigation(*args, **kwargs):
        raise NavigationError("navigation failed")

    monkeypatch.setattr(browser, "_navigate", fail_navigation)

    with pytest.raises(NavigationError):
        browser.open("https://example.com")

    assert playwright_page.closed is True
    assert browser._pages == []


def test_open_preserves_caller_owned_page_when_navigation_fails(monkeypatch):
    browser = Browser()
    monkeypatch.setattr(browser, "start", lambda: browser)
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    browser._pages.append(page)

    def fail_navigation(*args, **kwargs):
        raise NavigationError("navigation failed")

    monkeypatch.setattr(browser, "_navigate", fail_navigation)

    with pytest.raises(NavigationError):
        browser.open("https://example.com", page=page)

    assert playwright_page.closed is False
    assert browser._pages == [page]


def _register(browser, page):
    browser._pages.append(page)
    return page



def test_browser_fetch_passes_markdown_option_and_closes_page(monkeypatch):
    browser = Browser()

    class FakePage:
        def __init__(self):
            self.extract_kwargs = None
            self.closed = False

        def extract(self, **kwargs):
            self.extract_kwargs = kwargs
            return kwargs

        def close(self):
            self.closed = True

    page = FakePage()
    monkeypatch.setattr(browser, "open", lambda *args, **kwargs: page)

    result = browser.fetch(
        "https://example.com",
        include_html=True,
        include_links=True,
        include_markdown=True,
    )

    assert result == {
        "include_html": True,
        "include_links": True,
        "include_markdown": True,
    }
    assert page.extract_kwargs == result
    assert page.closed is True



def test_element_interaction_error_is_not_reported_as_missing(monkeypatch):
    from chromebrowse.browser import Element
    from chromebrowse.exceptions import ElementInteractionError

    class BrokenLocator:
        def nth(self, index):
            return self

        def click(self, **kwargs):
            raise RuntimeError("overlay intercepts click")

    class FakePage:
        def locator(self, selector):
            return BrokenLocator()

    element = Element.__new__(Element)
    element._page = type("Owner", (), {"_pw_page": FakePage(), "_timeout": 30000})()
    element._selector = "#submit"
    element._index = 0

    monkeypatch.setattr(Element, "_exists", lambda self: True)
    with pytest.raises(ElementInteractionError, match="overlay"):
        element.click()


def test_element_click_and_fill_preserve_zero_timeout(monkeypatch):
    from chromebrowse.browser import Element

    seen = []

    class Locator:
        def nth(self, index):
            return self

        def click(self, **kwargs):
            seen.append(("click", kwargs["timeout"]))

        def fill(self, value, **kwargs):
            seen.append(("fill", kwargs["timeout"]))

    class FakePage:
        def locator(self, selector):
            return Locator()

    owner = type("Owner", (), {"_pw_page": FakePage(), "_timeout": 30000})()
    element = Element.__new__(Element)
    element._page = owner
    element._selector = "#field"
    element._index = 0

    monkeypatch.setattr(Element, "_exists", lambda self: True)
    element.click(timeout=0)
    element.fill("x", timeout=0)

    assert seen == [("click", 0), ("fill", 0)]


def test_wait_methods_preserve_zero_timeout():
    from chromebrowse.browser import Page

    class FakePage:
        def __init__(self):
            self.timeouts = []

        def wait_for_selector(self, selector, **kwargs):
            self.timeouts.append(kwargs["timeout"])

        def wait_for_load_state(self, state, **kwargs):
            self.timeouts.append(kwargs["timeout"])

    browser = Browser()
    fake = FakePage()
    page = Page(browser, fake)

    page.wait_for("#ready", timeout=0)
    page.wait_for_load("load", timeout=0)

    assert fake.timeouts == [0, 0]
